import os
import os.path as osp
import click
import json
import sys
import getpass
import subprocess
from datetime import datetime
from collections import defaultdict
MAX_PODS_PER_USER=999
MAX_JOBS_PER_USER=999

@click.group()
def cli():
    pass

@click.command()
def get_pods_list():
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser()}')

@click.command()
def get_pods_num():
    out_pods_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser()} | wc -l')
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()} | wc -l')
    if 'No' not in out_pods_str:
      if 'No' not in out_jobs_str:
        jobs_num = int(out_jobs_str)
      else:
        jobs_num = 0
      print(int(out_pods_str) - jobs_num)
      return int(out_pods_str) - jobs_num
    else:
      print(0)
      return 0

@click.command()
@click.option('-n', '--ngpu', default=1)
@click.option('-c', '--cpu', default="4")
@click.option('-m', '--memory', default="4Gi")
@click.option('-t', '--template', default=None)
@click.option('-e', '--exp', default=None)
# @click.argument('exp')
def create_pod(ngpu, cpu, memory, template, exp):
    out_pods_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser()} | wc -l')
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()} | wc -l')
    if 'No' not in out_pods_str:
      if 'No' not in out_jobs_str:
        jobs_num = int(out_jobs_str)
      else:
        jobs_num = 0
      if int(out_pods_str) - jobs_num > MAX_PODS_PER_USER:
        print(f'\nSORRY, you only can have {MAX_PODS_PER_USER} Pods at the same time.\n\nCurrent pods:')
        os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser()}')
        return
    
    assert exp is not None, "Exp cannot be empty"
    
    exp = json.load(open(exp, 'r'))
    name = getpass.getuser() + '-' + exp['name'] + datetime.now().strftime("-%m-%d-%H-%M-%S") + str(hash(exp))
    if template is not None:
        # yml_dict = json.load(open(template, 'r'))
        # yml_dict = defaultdict(lambda: defaultdict(dict), yml_dict)
        nested_dict = lambda: defaultdict(nested_dict)
        yml_dict = nested_dict()
        yml_dict.update(json.load(open(template, 'r')))
        # exp = nested_dict().update(json.load(open(exp, 'r')))
        
        yml_dict["metadata"]["name"] = name
        yml_dict["metadata"]["namespace"] = "default" if "namespace" not in exp else exp["namespace"]
        
        yml_dict["metadata"]["labels"]["app"] = "default" if "labels" not in exp else exp["labels"]
        
        yml_dict["spec"]["containers"]["image"] = yml_dict["spec"]["containers"]["image"] if "image" not in exp else exp["image"]
        yml_dict["spec"]["containers"]["args"] = ["bash"] if "args" not in exp else exp["args"]
        yml_dict["spec"]["containers"]["resources"]["limits"]["nvidia.com/gpu"] = ngpu
        yml_dict["spec"]["containers"]["resources"]["limits"]["cpu"] = cpu
        yml_dict["spec"]["containers"]["resources"]["limits"]["memory"] = memory
         
    else:
        yml_str = f"apiVersion: v1\n\
kind: Pod\n\
metadata:\n\
  namespace: {getpass.getuser()}\n\
  name: {name}\n\
  labels:\n\
    app: {getpass.getuser()}\n\
spec:\n\
  securityContext:\n\
    fsGroup: 0\n\
  volumes:\n\
    - name: algo-nas\n\
      hostPath:\n\
        path: /mnt/nas\n\
    - name: dshm\n\
      emptyDir:\n\
        medium: Memory\n\
  containers:\n\
    - name: container\n\
      command: [ '/bin/bash', '-c', '--' ]\n\
      args: [ 'cd {exp['folder']} && {exp['cmd']} && sleep 86400' ]\n\
      image: {exp['image']}\n\
      resources:\n\
        limits:\n\
          nvidia.com/gpu: {ngpu}\n\
      volumeMounts:\n\
        - mountPath: /dev/shm\n\
          name: dshm\n\
        - mountPath: /mnt/nas\n\
          name: algo-nas"
    with open('tmp.yml', 'w') as f:
        f.write(yml_str)
    print('Creating a Pod with config\n' + json.dumps(exp, indent=2))
    os.system('export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl apply -f tmp.yml && rm -rf tmp.yml')

@click.command()
@click.argument('name')
def delete_pod(name):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl delete pod {name} --namespace {getpass.getuser()} &')

@click.command()
def delete_all_pods():
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl delete pods --all --namespace {getpass.getuser()} &')

@click.command()
@click.argument('name')
def attach_pod(name):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl exec {name} --namespace {getpass.getuser()} -it -- /bin/bash')

@click.command()
@click.argument('name')
def logs_pod(name):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl logs {name} --namespace {getpass.getuser()}')

@click.command()
def get_jobs_list():
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()}')

@click.command()
def get_jobs_num():
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()} | wc -l')
    if 'No' in out_jobs_str:
      print(0)
      return 0
    else:
      print(int(out_jobs_str) - 1)
      return int(out_jobs_str) - 1

@click.command()
@click.option('-n', '--ngpu', default=1)
@click.argument('exp')
def create_job(ngpu, exp):
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()} | wc -l')
    if 'No' not in out_jobs_str:
      jobs_num = int(out_jobs_str)
      if jobs_num > MAX_JOBS_PER_USER:
        print(f'\nSORRY, you only can have {MAX_JOBS_PER_USER} Pods at the same time.\n\nCurrent pods:')
        os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser()}')
        return

    exp = json.load(open(exp, 'r'))
    name = getpass.getuser() + '-' + exp['name'] + datetime.now().strftime("-%m-%d-%H-%M-%S")   
    yml_str = f"apiVersion: batch/v1\n\
kind: Job\n\
metadata:\n\
  namespace: {getpass.getuser()}\n\
  name: {name}\n\
  labels:\n\
    app: {getpass.getuser()}\n\
spec:\n\
  ttlSecondsAfterFinished: 5\n\
  backoffLimit: 120\n\
  template:\n\
    spec:\n\
      restartPolicy: Never\n\
      dnsPolicy: ClusterFirst\n\
      schedulerName: default-scheduler\n\
      tolerations:\n\
        - key: nvidia.com/gpu\n\
          operator: Exists\n\
          effect: NoSchedule\n\
      volumes:\n\
        - name: algo-nas\n\
          hostPath:\n\
              path: /mnt/nas\n\
        - name: dshm\n\
          emptyDir:\n\
              medium: Memory\n\
      containers:\n\
        - name: container\n\
          command: [ '/bin/bash', '-c', '--' ]\n\
          args: [ 'cd {exp['folder']} && {exp['cmd']}' ]\n\
          image: {exp['image']}\n\
          resources:\n\
              limits:\n\
                nvidia.com/gpu: {ngpu}\n\
          volumeMounts:\n\
            - mountPath: /dev/shm\n\
              name: dshm\n\
            - mountPath: /mnt/nas\n\
              name: algo-nas"
    with open('tmp.yml', 'w') as f:
        f.write(yml_str)
    print('Creating a Job with config\n' + json.dumps(exp, indent=2))
    os.system('export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl apply -f tmp.yml && rm -rf tmp.yml')

@click.command()
@click.argument('name')
def delete_job(name):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl delete job {name} --namespace {getpass.getuser()} &')

@click.command()
def delete_all_jobs():
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl delete jobs --all --namespace {getpass.getuser()} &')

cli.add_command(get_pods_list)
cli.add_command(get_pods_num)
cli.add_command(create_pod)
cli.add_command(delete_pod)
cli.add_command(delete_all_pods)
cli.add_command(attach_pod)
cli.add_command(logs_pod)
cli.add_command(get_jobs_list)
cli.add_command(get_jobs_num)
cli.add_command(create_job)
cli.add_command(delete_job)
cli.add_command(delete_all_jobs)

if __name__ == '__main__':
    cli()