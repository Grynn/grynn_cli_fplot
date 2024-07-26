.PHONY: install

install:
	@echo "Installing editable package"
	pip install -e .

venv: 
	@echo "Creating virtual environment"
	python3 -m venv venv
	@echo "Activating virtual environment"
	@echo "Run 'deactivate' to exit the virtual environment"
	@echo "Run 'source venv/bin/activate' to re-enter the virtual environment"
	@echo "Run 'make install' to install the package in editable mode"
	