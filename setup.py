from setuptools import setup, find_packages

setup(
    name='historical_quote',
    version='0.2.0',
    py_modules=['main'],
    install_requires=[
        'Click',
    ],
    entry_points={
        'console_scripts': [
            'historical_quote=main:generate_plot'
        ]
    }    
)
