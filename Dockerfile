FROM apify/actor-python:3.14
COPY --chown=myuser:myuser requirements.txt ./
RUN pip install -r requirements.txt && pip freeze
COPY --chown=myuser:myuser . ./
RUN python -m compileall -q aws_ip_range_diff/
CMD ["python", "-m", "aws_ip_range_diff"]
