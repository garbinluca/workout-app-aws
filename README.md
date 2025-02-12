# Workout App

APP per la gestione di allenamenti in palestra basati sul protocollo Strongfits 5x5. 

Questo progetto fornisce tre soluzioni:
- metodo che viene invocato due volte alla settimana che crea il WOD giornaliero e che lo invia tramite API esterna
- metodo di GET dell'allenamento
- metodo di PUT dell'allenamento
Stack tecnologico:
- Python
- AWS DynamoDB
- AWS SAM

```bash
# Comandi
sam build
sam deploy
```

*Non presenti nel repo: semplice pagina HTML che legge i dati e invia l'aggiornamento dell'attività*