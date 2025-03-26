from setuptools import setup, find_packages

setup(
    name="coodb",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "sortedcontainers>=2.4.0",
        "pygtrie>=2.5.0",
        "BTrees>=4.11.3"
    ],
    python_requires=">=3.7",
    author="xisun",
    description="A Python implementation of Bitcask",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
) 