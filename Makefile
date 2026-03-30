.PHONY: deploy unit-testing lint format install bootstrap synth diff

install:
	uv sync

lint:
	uv run ruff check src/ tests/

format:
	uv run ruff format src/ tests/

unit-testing:
	uv run pytest --cov=src --cov-report=term-missing

deploy: install lint unit-testing synth
	PYTHONPATH=. cdk deploy --all --profile gsti-us --app "python cdk/app.py"

bootstrap:
	PYTHONPATH=. cdk bootstrap --profile gsti-us --app "python cdk/app.py"

synth:
	PYTHONPATH=. cdk synth --app "python cdk/app.py"

diff:
	PYTHONPATH=. cdk diff --profile gsti-us --app "python cdk/app.py"
