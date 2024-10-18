.PHONY: install

install:
	poetry install

.PHONY: clean
clean:
	rm -rf dist
	rm -rf __pycache__