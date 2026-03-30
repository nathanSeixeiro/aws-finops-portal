.PHONY: deploy unit-testing lint format install bootstrap synth diff

install:
	uv sync

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

unit-testing:
	uv run pytest --cov=src --cov-report=term-missing

deploy:
	cd cdk && cdk deploy --all --profile gsti-us

bootstrap:
	cd cdk && cdk bootstrap --profile gsti-us

synth:
	cd cdk && cdk synth

diff:
	cd cdk && cdk diff --profile gsti-us
