# Scheduling OMERO.RuleTagger

## Using a Kubernetes CronJob

A Kubernetes CronJob can run the container on a defined schedule. Here is an example YAML:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
    name: omero-ruletagger-cronjob
spec:
    schedule: "0 0 * * *"
    jobTemplate:
        spec:
            template:
                spec:
                    containers:
                        - name: ruletagger
                            image: ghcr.io/laviolette-lab/omero-ruletagger:1.0.0
                            args:
                                - "python3 /app/src/omero_ruletagger/__main__.py /config/tag_rules.yml ...
                                     -s  ${OMERO_SERVER} -p  ${OMERO_PORT} -u  ${OMERO_USERNAME} -w  ${OMERO_PASSWORD} ...
                                     $([ ! -z $OMERO_SECURE ] && echo '-S')"
                    restartPolicy: OnFailure
```

Provide configuration and secrets (e.g., `omero-connection-secret`) to store credentials securely. See the k8s directory for example CRDs.

## Using a Standard Cron

On a Linux system, open the crontab with:

```bash
crontab -e
```

Add an entry to run the script periodically. For example, to run every midnight:

```bash
0 0 * * * /usr/bin/python3 -m omero_ruletagger /path/to/tag_rules.yml -s localhost -u username -w password
```

Adjust the schedule, paths, and connection settings as needed.