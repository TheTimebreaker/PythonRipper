FROM python:3.14.3

#workdir
WORKDIR /app

# copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy code
COPY ./pythonripper .

# generate machine-id for plyer. doesnt actually need to be official, the file just needs to be there
RUN cat /proc/sys/kernel/random/uuid > /etc/machine-id

# run script by default
ENTRYPOINT [ "python" ]
CMD ["-m", "scripts.update_scheduler"]