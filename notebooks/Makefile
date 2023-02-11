.DEFAULT_GOAL := build
CEPH_DIR = /mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log/

install:
	python3.8 -m venv venv/
	venv/bin/pip install --upgrade pip
	venv/bin/pip install venv-pack seaborn matplotlib fasttext-langdetect pyspark pyarrow pandas

build: install
	venv/bin/venv-pack --prefix venv/ --output ${CEPH_DIR}/venv.tar.gz --force