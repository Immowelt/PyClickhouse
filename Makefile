test: run
	# start container, run tests with tox and stop container, so it gets removed
	tox || ${MAKE} stop
	
run:
	# start local temporary clickhouse server: https://github.com/yandex/ClickHouse/tree/master/docker/server
	docker run -d -p 8123:8123 -p 9000:9000 --rm --name clickhouse-test-server --ulimit nofile=262144:262144 yandex/clickhouse-server

stop:
	docker stop clickhouse-test-server || true

build:
	sh ./build.sh

to_3:
	rm -f Pipfile.lock
	pipenv install --dev --python 3

to_2:
	rm -f Pipfile.lock
	pipenv install --dev --python 2.7


.PHONY: test run stop build
