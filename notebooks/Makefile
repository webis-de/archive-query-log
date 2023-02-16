CEPH_DIR = /mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log

install:
	test -d ${CEPH_DIR}/venv || python3.8 -m venv ${CEPH_DIR}/venv
	${CEPH_DIR}/venv/bin/pip install --upgrade pip
	${CEPH_DIR}/venv/bin/pip install venv-pack seaborn matplotlib langdetect fasttext-langdetect pyspark pyarrow pandas tqdm fastwarc
