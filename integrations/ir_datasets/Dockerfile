FROM webis/tira-ir-datasets-starter:0.0.54

RUN apk add jq libffi-dev openjdk11
RUN pip3 install tira python-terrier jupyter repro_eval

# The ir_datasets integration in "long_eval_ir_datasets_integration.py" needs to be
# located in a package "datasets_in_progress" on the pythonpath so that they can be found. The following copy command ensures this.
# You can test that it is correctly in the python path by running "from ir_datasets.datasets_in_progress import long_eval_ir_datasets_integration" inside a python shell.
COPY archive_query_log_ir_datasets_integration.py /usr/lib/python3.8/site-packages/ir_datasets/datasets_in_progress/

COPY data/ /data/

ENTRYPOINT [ "/irds_cli.sh" ]
