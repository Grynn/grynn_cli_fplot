.PHONY: install clean

install:
	pip install -e .

clean:
	rm -rf ./dist
	rm -rf __pycache__
	rm -rf ./venv