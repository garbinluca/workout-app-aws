# Workout App

```
# Creazione layer
python3.12 -m venv venv
source venv/bin/activate
mkdir python
cd python
pip install numpy -t .
cd ..
zip -r workout-layers.zip python
# Download /home/cloudshell-user/packages/workout-layers.zip

```

```
# Creazione layer
mkdir -p layer/python
cd layer/python
pip install requests -t .
cd ../..

```


```
# Costruisce il package
sam build

# Deploya l'applicazione (interattivo)
sam deploy --guided

# Per i deploy successivi puoi usare semplicemente
sam deploy

# updates
sam build && sam deploy

```