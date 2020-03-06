# PyClickhouse
Minimalist Clickhouse Python driver with an API roughly resembling Python DB API 2.0 specification.

## Developer info

### Pipfile

The [Pipfile](Pipfile) in this project omits the python version (section `[requires]`), to keep
this project compatible with Python 2 and 3. 

To develop or run anything in this project, it is recommended to setup a virtual
environment using the provided Pipfile:

````bash
    pipenv install --dev
````

As it is, this command will create a virtual environment with the current `python`
interpreter used in the system. The version of the python interpreter may be
changed with the `--python` switch when installing:

````bash
    # remove lock file to avoid version conflicts
    rm Pipfile.lock
    # substitute 2.7 for the desired python version, e.g. 3.6
    pipenv install --python 2.7
````

This will recreate the virtual environment as well, if necessary.

### Makefile and running tests

The [Makefile](Makefile) target `test` is provided to run the project's tests. Some require
access to a running instance of Clickhouse, which may provided through docker. 

The tests are run with [tox](https://tox.readthedocs.io/en/latest/) via `make test`, with uses 
pipenv to create virtual environments for each of the python versions being tested. Currently 
Python 2.7 and 3.7 are configured (see [tox.ini](./tox.ini)). 

Tox should be available outside the project, as it creates it's own environments:

````bash
pip install --user tox
````

Convenience make targets are provided to manage a local Clickhouse instance via Docker. They
assume that docker is installed and the current user can use it without sudo (or use sudo to
run these targets). The Clickhouse Server will be available on `localhost:8123`.

- `run`: starts the clickhouse container
- `stop`: stops the clickhouse container

Additional targets:

- `build`: runs the `build.sh` script
- `to_2`: reconfigures the environment to use python 2
- `to_3`: reconfigures the environment to use python 3
