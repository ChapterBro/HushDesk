.PHONY: trial install
install:
	python3 -m venv .venv && . .venv/bin/activate && python -m pip install -U pip wheel && python -m pip install pymupdf
trial:
	chmod +x bin/hush && bin/hush trial
