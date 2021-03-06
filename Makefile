.DEFAULT_GOAL := all

.PHONY: install
install:
	pip install -r requirements.txt

.PHONY: isort
isort:
	isort -rc -w 120 -sg */run.py src
	isort -rc -w 120 tests

.PHONY: lint
lint:
	flake8 src/ tests/
	pytest src -p no:sugar -q --cache-clear
	cd js; yarn lint; cd ..

.PHONY: test
test:
	pytest --cov=src

.PHONY: testcov
testcov: test
	coverage html

.PHONY: all
all: testcov lint
