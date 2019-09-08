# Tvilling Digital
Tvilling Digital is an extensible prototype for a cloud based digital twin platform.

## Installation
After cloning the repository and installing python run
```bash
pip install -r requirements.txt
```
inside the cloned repository to install required internal dependencies.

To change the configuration of the prototype, for example the ports the prototype will use or the location of the Apache Kafka server, change the `settings.py` file.

Apache Kafka has to be running and available before the prototype can be started.

Start the prototype by executing the `main.py` file.
This can be done by for example running
```bash
python main.py
```
inside the cloned repository.

## Usage
The API documentation can be seen by visiting the `/docs/` page in the browser while the application is running.
A simple web application used for testing purposes is found by visiting the `/` page.

The prototype has to receive some kind of data from somewhere before anything interesting can happen.
The easiest way to accomplish this is to send data through UDP as bytearrays to the prototype.
A datasource object can the be added for this data source on `/datasources/create`, more information can be found on the `/docs/datasources/` page.

Blueprints must be placed in the folder specified by `BLUEPRINT_DIR` in the `settings.py` file.
Some blueprints are already included, one of these is the `fmu` blueprint used to simulate FMUs.
FMUs must be placed in the folder specified by `FMU_DIR` in the `settings.py` file before they can be used.
