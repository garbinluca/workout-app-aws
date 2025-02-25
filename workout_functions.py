import boto3
import json
from datetime import datetime, timedelta
import pytz
from decimal import Decimal
import requests
import os
import uuid

# Inizializza il client DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('workout-table')


def get_last_workout_by_type(type):
    response = table.query(
        IndexName='wod_type_index',
        Limit=1,
        ScanIndexForward=False,
        KeyConditionExpression='wod_type = :wod_type',
        ExpressionAttributeValues={
            ':wod_type': type
        }
    )

    items = response.get('Items', [])
    return items[0] if items else None


def get_last_workout():
    tz = pytz.timezone('Europe/Rome')
    current_date = datetime.now(tz).date()

    workoutA = get_last_workout_by_type('A')
    workoutB = get_last_workout_by_type('B')

    if workoutA['scheduled_date'] > workoutB['scheduled_date']:
        return workoutA
    else:
        return workoutB


def create_next_workout(event, context):
    """
    Lambda function per creare il prossimo workout
    Viene eseguita tramite CloudWatch Events alle 8:00 IT il martedì e giovedì
    """
    # Converti l'ora corrente in timezone italiana
    tz = pytz.timezone('Europe/Rome')
    current_date = datetime.now(tz).date()

    # Verifica se esiste già un workout per oggi
    response = table.query(
        IndexName='workout-date-index',
        KeyConditionExpression='scheduled_date = :date',
        ExpressionAttributeValues={
            ':date': current_date.isoformat()
        }
    )

    if response['Items']:
        return {
            'statusCode': 200,
            'body': json.dumps('Workout già esistente per oggi')
        }

    last_workout = get_last_workout()

    if last_workout and last_workout.get('completed') is not False:
        # Se l'ultimo workout non è stato completato, lo riproponiamo
        last_id = last_workout.get('id')
    else:
        # Determina il tipo del nuovo workout (A o B)
        new_type = 'B' if last_workout and last_workout['wod_type'] == 'A' else 'A'

        # Trova l'ultimo workout completato dello stesso tipo
        response = table.scan(
            FilterExpression='wod_type = :wod_type AND completed = :completed',
            ExpressionAttributeValues={
                ':wod_type': new_type,
                ':completed': True
            }
        )
        last_same_type = max(response['Items'], key=lambda x: x['scheduled_date']) if response['Items'] else None

        # Calcola i nuovi pesi
        weight_increment = Decimal('2.5')
        lastWeightEx1 = Decimal(last_same_type['exercise1_weight'])
        lastWeightEx2 = Decimal(last_same_type['exercise2_weight'])
        lastWeightEx3 = Decimal(last_same_type['exercise3_weight'])

        last_workout = {
            'id': str(uuid.uuid1()),
            'scheduled_date': current_date.isoformat(),
            'wod_type': new_type,
            'exercise1_weight': (lastWeightEx1 + weight_increment) if last_same_type and last_same_type['increase_weight1'] else Decimal('20.0'),
            'exercise2_weight': (lastWeightEx2 + weight_increment) if last_same_type and last_same_type['increase_weight2'] else Decimal('20.0'),
            'exercise3_weight': (lastWeightEx3 + weight_increment) if last_same_type and last_same_type['increase_weight3'] else Decimal('20.0'),
            'increase_weight1': True,
            'increase_weight2': True,
            'increase_weight3': True,
            'completed': False
        }
        table.put_item(Item=last_workout)
        last_id = last_workout['id']

    # Invia la notifica all'API esterna
    send_message(last_id, last_workout)

    return {
        'statusCode': 200,
        'body': json.dumps('Nuovo workout creato con successo')
    }


def get_workout(event, context):
    """
    API GET per recuperare le informazioni di un workout specifico
    """
    workout_id = event['pathParameters']['id']

    try:
        response = table.get_item(
            Key={'id': workout_id}
        )

        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps('Workout non trovato')
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response['Item'], default=str)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Errore: {str(e)}')
        }


def update_workout(event, context):
    """
    API PUT per aggiornare le informazioni di un workout
    """
    workout_id = event['pathParameters']['id']
    body = json.loads(event['body'])

    update_expression = 'SET '
    expression_values = {}

    tz = pytz.timezone('Europe/Rome')
    body['completed'] = True
    body['completed_at'] = str(datetime.now(tz))

    # Campi aggiornabili
    updatable_fields = [
        'increase_weight1',
        'increase_weight2',
        'increase_weight3',
        'exercise1_weight',
        'exercise2_weight',
        'exercise3_weight',
        'completed',
        'completed_at'
    ]

    # Costruisci l'espressione di update dinamicamente
    for field in updatable_fields:
        if field in body:
            update_expression += f'#{field} = :{field}, '
            expression_values[f':{field}'] = body[field]

    # Rimuovi l'ultima virgola e spazio
    update_expression = update_expression[:-2]

    # Crea il dizionario per i nomi degli attributi
    expression_names = {f'#{field}': field for field in updatable_fields if field in body}

    try:
        response = table.update_item(
            Key={'id': workout_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues='ALL_NEW'
        )

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response['Attributes'], default=str)
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps(f'Errore: {str(e)}')
        }


def send_message(id, workout):
    NOTIFICATION_API_ENDPOINT = os.environ['NOTIFICATION_API_ENDPOINT']
    FRONT_URL = os.environ['FRONT_URL']

    link = f"{FRONT_URL}/workout/{id}"

    message = '🏋🏻‍♂️ *WORKOUT OF THE DAY*:\n'

    weight1 = workout['exercise1_weight']
    weight2 = workout['exercise2_weight']
    weight3 = workout['exercise3_weight']

    if workout['wod_type'] == 'A':
        message = message + f'SQUAT: {weight1}\n'
        message = message + f'PANCA PIANA: {weight2}\n'
        message = message + f'REMATORE: {weight3}\n'
    else:
        message = message + f'SQUAT: {weight1}\n'
        message = message + f'MILITARY PRESS: {weight2}\n'
        message = message + f'STACCHI: {weight3}\n\n'

    message = message + f'>> [FATTO!]({link})\n\n'
    message = message + 'Ricorda *GARMIN* e *BORRACCIA*'

    try:
        payload = {
            'Records': [
                {
                    'EventSource': 'ws',
                    'Message': message
                }
            ]
        }

        api_response = requests.post(
            NOTIFICATION_API_ENDPOINT,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=5  # Timeout di 5 secondi
        )
        api_response.raise_for_status()  # Solleva un'eccezione per status code >= 400

    except requests.exceptions.RequestException as e:
        print(f"Errore nell'invio della notifica all'API esterna: {str(e)}")
        # Decidi se vuoi gestire l'errore in modo particolare
        # Per ora logghiamo l'errore ma continuiamo l'esecuzione


def get_workouts(event, context):
    response = table.scan()
    items = response['Items']

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response['Items'])

    items = sorted(items, key=lambda x: x['scheduled_date'], reverse=True)

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(items, default=str)
    }
