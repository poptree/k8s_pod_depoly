import os
import os.path as osp
import click
import json
import yaml
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
@click.option('-n', '--namespace', default="default")
def get_pods_list(namespace):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser() if namespace is None else namespace}')

@click.command()
@click.option('-n', '--namespace', default="default")
def get_pods_num(namespace):
    out_pods_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser() if namespace is None else namespace} | wc -l')
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser() if namespace is None else namespace} | wc -l')
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


import subprocess


import subprocess
import json
@click.command()
def get_gpu_usage():
	command = (
		"export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl describe nodes | "
		"tr -d '\\000' | "
		"sed -n -e '/^Name/,/Roles/p' -e '/^Capacity/,/Allocatable/p' -e '/^Allocated resources/,/Events/p' | "
		"grep -e Name -e nvidia.com | "
		"perl -pe 's/\\n//' | "
		"perl -pe 's/Name:/\\n/g' | "
		"sed 's/nvidia.com\\/gpu:\\?//g' | "
		"sed '1s/^/Node Available(GPUs)  Used(GPUs)/' | "
		"sed 's/$/ 0 0 0/' | "
		"awk '{print $1, $2, $3}' | "
		"column -t"
	)

	# 执行命令并获取输出
	output = subprocess.getoutput(command)

	# 打印输出
	print(output)


@click.command()
@click.option('-n', '--ngpu', default=1)
@click.option('-ns', '--namespace', default="default")
@click.option('-c', '--cpu', default="16")
@click.option('-m', '--memory', default="32Gi")
@click.option('-t', '--template', default=None)
@click.option('-e', '--exp', default=None)
@click.option('-a', '--args', default=None)
# @click.argument('exp')
def create_pod(ngpu, cpu, memory, template, exp, args, namespace):
    out_pods_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser() if namespace is None else namespace} | wc -l')
    out_jobs_str = subprocess.getoutput(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get jobs --namespace {getpass.getuser() if namespace is None else namespace} | wc -l')
    if 'No' not in out_pods_str:
      if 'No' not in out_jobs_str:
        jobs_num = int(out_jobs_str)
      else:
        jobs_num = 0
      if int(out_pods_str) - jobs_num > MAX_PODS_PER_USER:
        print(f'\nSORRY, you only can have {MAX_PODS_PER_USER} Pods at the same time.\n\nCurrent pods:')
        os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --namespace {getpass.getuser() if namespace is None else namespace} ')
        return
    
    assert exp is not None, "Exp cannot be empty"
    
    exp = yaml.load(open(exp, 'r'), Loader=yaml.FullLoader)
    if args is not None:
      exp["cmd"] = args
    print(yaml.dump(exp, indent=2))
    name = getpass.getuser() + '-' + exp['name'] + datetime.now().strftime("-%m-%d-%H-%M-%S")
    if template is not None:
        # yml_dict = json.load(open(template, 'r'))
        # yml_dict = defaultdict(lambda: defaultdict(dict), yml_dict)
        # nested_dict = lambda: defaultdict(nested_dict)
        # yml_dict = nested_dict()
        # yml_dict.update(yaml.load(open(template, 'r'), Loader=yaml.FullLoader))
        # exp = nested_dict().update(json.load(open(exp, 'r')))
        yml_dict = yaml.load(open(template, 'r'), Loader=yaml.FullLoader)
        yml_dict["metadata"]["name"] = name
        yml_dict["metadata"]["namespace"] = getpass.getuser() if "namespace" not in exp else exp["namespace"]
        yml_dict["metadata"]["namespace"] = yml_dict["metadata"]["namespace"] if namespace is None else namespace
        
        yml_dict["metadata"]["labels"] = yml_dict["metadata"]["labels"] if "labels" in yml_dict["metadata"] else {}
        
        yml_dict["metadata"]["labels"]["app"] = getpass.getuser() if "labels" not in exp else exp["labels"]
        
        yml_dict["spec"]["containers"][0]["image"] = yml_dict["spec"]["containers"]["image"] if "image" not in exp else exp["image"]
        yml_dict["spec"]["containers"][0]["args"] = ["bash"] if "cmd" not in exp else [exp["cmd"]]
        yml_dict["spec"]["containers"][0]["resources"]["limits"]["nvidia.com/gpu"] = ngpu
        yml_dict["spec"]["containers"][0]["resources"]["limits"]["cpu"] = cpu
        yml_dict["spec"]["containers"][0]["resources"]["limits"]["memory"] = memory
        yml_str = yaml.dump(yml_dict, indent=2)
         
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
    print(yml_str)
    os.system('export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl apply -f tmp.yml && rm -rf tmp.yml')

@click.command()
@click.argument('name')
@click.option('-n', '--namespace', default="default")
def delete_pod(name,namespace):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl delete pod {name} --namespace {getpass.getuser() if namespace is None else namespace} &')

@click.command()
@click.argument('name')
@click.option('-n', '--namespace', default="default")
def attach_pod(name,namespace):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl exec {name} --namespace {getpass.getuser() if namespace is None else namespace} -it -- /bin/bash')

@click.command()
@click.argument('name')
@click.option('-n', '--namespace', default="default")
def logs_pod(name,namespace):
    os.system(f'export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl logs {name} --namespace {getpass.getuser() if namespace is None else namespace}')






cli.add_command(get_pods_list)
cli.add_command(get_pods_num)
cli.add_command(create_pod)
cli.add_command(delete_pod)
cli.add_command(attach_pod)
cli.add_command(logs_pod)
cli.add_command(get_gpu_usage)

if __name__ == '__main__':
    cli()