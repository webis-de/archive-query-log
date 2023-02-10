install:
	pip install pex
build-pex: install
	pex -v --python python3.8 --output-file notebooks.pex\
	 	seaborn matplotlib fasttext-langdetect
build: build-pex