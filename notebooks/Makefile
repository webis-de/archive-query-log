CEPH_DIR = /mnt/ceph/storage/data-in-progress/data-research/web-search/web-archive-query-log

install:
	echo "Important: You MUST run this from a machine that has python3.8 linked to the exact same location as all Spark nodes."
	python3.8 -m venv --symlinks ${CEPH_DIR}/venv
	${CEPH_DIR}/venv/bin/python -m pip install --upgrade pip
	${CEPH_DIR}/venv/bin/python -m pip install venv-pack seaborn matplotlib pycld3 pyspark pyarrow pandas tqdm fastwarc bleach beautifulsoup4
