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

The [Makefile](Makefile) target `test` is provided to run the project's tests. These require
access to a running instance of Clickhouse, which is provided through docker. This assumes
that docker is installed and the current user can use it without sudo.

A one-liner to run the tests in the virtual environment would be:

````bash
    pipenv run make test
````

Additional targets:

- `run`: starts the clickhouse container
- `stop`: stops the clickhouse container
- `build`: runs the `build.sh` script
- `to_2`: removes Pipfile.lock and configures the environment to use python 2
- `to_3`: removes Pipfile.lock and configures the environment to use python 3
