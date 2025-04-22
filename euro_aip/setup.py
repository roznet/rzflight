from setuptools import setup, find_packages

setup(
    name="euro_aip",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.25.1",
        "pandas>=1.2.0",
        "camelot-py>=0.10.1",
        "sqlalchemy>=1.4.0",
        "python-dateutil>=2.8.1",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "black>=21.0",
            "mypy>=0.900",
            "flake8>=3.9.0",
        ]
    },
    author="Brice Rosenzweig",
    author_email="brice@rosenzweig.io",
    description="A library for parsing and managing European AIP (Aeronautical Information Publication) data",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/brice/euro_aip",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    python_requires=">=3.8",
) 