IMAGE_VERSION=0.0.1

build-docker-images:
	cd ../.. \
	&& docker build -t mam10eks/archive-query-log-ir-datasets-integration:${IMAGE_VERSION} -f archive_query_log/ir_datasets/Dockerfile.ir_datasets .

push-docker-images:
	docker push mam10eks/archive-query-log-ir-datasets-integration:${IMAGE_VERSION}
