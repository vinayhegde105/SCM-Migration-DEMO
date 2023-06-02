import pandas as pd
import requests
import subprocess
from urllib.parse import quote
import time
import shutil
import os
import stat


# Read Excel file
df = pd.read_excel('./ado-bitbucket/azure-to-bitbucket.xlsx')

# print("")
# bitbucket_username = input("Enter the Bitbucket usernme: ")
# print("")
# bitbucket_password = input("Enter the Bitbucket app password: ")
# print("")
# azure_token = input("Enter the Azure Repos personal access token: ")
# print("")
# gitlab_token = input("Enter the GitLab access token: ")
# print("")
# print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
bitbucket_username = os.getenv('BITBUCKET_USERNAME')
bitbucket_password = os.getenv('BITBUCKET_PASSWORD')
azure_token = os.getenv('AZURE_TOKEN')
gitlab_token =os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')

encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing Azure to BitBucket")
print("")
bitbucket_urls = []
clone=[]
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    azure_project_namespace = row['azure_namespace']
    repo_to_import = row['repo_to_import']
    bitbucket_workspace_id = row['bitbucket_workspace_id']
    bitbucket_project_key = row['bitbucket_project_key']

    repo_data = {
        "scm": "git",
        "is_private": True,
        "project": {
            "key": f"{bitbucket_project_key}"
        }
    }
    api = f"https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_to_import.lower()}"
    headers = {
        'Content-Type': 'application/json',
    }
    auth=(bitbucket_username,bitbucket_password)
    response = requests.post(api, json=repo_data, headers=headers,auth=auth)
    if response.status_code == 200:
        print(f"Successfully created repository {repo_to_import} on BitBucket.")
        time.sleep(5)
    else:
        error_message = f"Error occurred while creating the repository {repo_to_import} with status code: {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_to_import, response.status_code, error_message])
        print("")
    print("")
    clone_url = f"https://azure:{azure_token}@dev.azure.com/{azure_project_namespace}/_git/{repo_to_import}"
    mirror_clone_path = f"./{repo_to_import}"
    clone_process = subprocess.run(["git", "clone", "--mirror", clone_url, mirror_clone_path], capture_output=True)
    if clone_process.returncode == 0:
        print(f"Mirror clone created successfully for {repo_to_import}.")
        clone.append(repo_to_import)
        print("")
    else:
        error_message=f"Error occurred while creating the mirror clone for {repo_to_import}. Return code: {clone_process.returncode}"
        print(error_message)
        failure_data.append([repo_to_import, clone_process.returncode, error_message])
        print("Error output:", clone_process.stderr.decode())
        print("")

    push_url = f"https://{bitbucket_username}:{bitbucket_password}@bitbucket.org/{bitbucket_workspace_id}/{repo_to_import}.git"
    push_process = subprocess.run(["git", "push", "--mirror", push_url], cwd=mirror_clone_path, capture_output=True)
    if push_process.returncode == 0:
        print(f"Mirror clone pushed to Bitbucket repository {repo_to_import} successfully.")
        bitbucket_urls.append(f'https://bitbucket.org/{bitbucket_workspace_id}/{repo_to_import}.git')
        success_data.append([repo_to_import, push_process.returncode])
        time.sleep(15)
        print("")
        url = f'https://dev.azure.com/{azure_project_namespace}/_apis/git/repositories/{repo_to_import}?api-version=7.0'
        response = requests.get(url, auth=("",azure_token))
        if response.status_code == 200:
            repo_data = response.json()
            default_branch_ref = repo_data['defaultBranch']
            default_branch = default_branch_ref.split('/')[-1]
        else:
            print(f"Failed to retrieve repository default branch. Status code: {response.status_code}")
        ##Azure Brach count
        print(f"Source Repository - {repo_to_import} branch validation is in progress...")
        url = f'https://dev.azure.com/{azure_project_namespace}/_apis/git/repositories/{repo_to_import}/refs?filter=heads/&api-version=7.0'
        params = {'searchCriteria.itemVersion.versionType': 'branch', 'searchCriteria.itemVersion.version': f'{default_branch}'}
        response = requests.get(url, auth=("", azure_token),params=params)

        if response.status_code == 200:
            branch_data = response.json()
            branch_count = len(branch_data['value'])
            azure_branches=branch_count
        else:
            print(f'Request failed with status code {response.status_code}')
        ## Azure Commit Count
        print(f"Source Repository - {repo_to_import} commit validation is in progress...")
        url = f'https://dev.azure.com/{azure_project_namespace}/_apis/git/repositories/{repo_to_import}/commits?api-version=7.0'

        commit_count = 0
        page_size = 100
        params = {'$top': page_size, '$skip': 0, 'searchCriteria.itemVersion.versionType': 'branch', 'searchCriteria.itemVersion.version': f'{default_branch}'}

        while True:
            response = requests.get(url, auth=("", azure_token), params=params)

            if response.status_code == 200:
                branch_data = response.json()
                commits = branch_data['value']
                commit_count += len(commits)

                if len(commits) == page_size:
                    params['$skip'] += page_size
                else:
                    break  # All commits retrieved
            else:
                print(f'Request failed with status code {response.status_code}')
                break
        azure_commit_count=commit_count
        ##bitbucket branch count
        print(f"Target Repository - {repo_to_import} branch validation is in progress...")
        auth=(bitbucket_username,bitbucket_password)
        url = f'https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_to_import}/refs/branches?pagelen=100'
        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            branch_data = response.json()
            total_branches = branch_data['size']
            bitbucket_branches=total_branches
        else:
            print(f'Request failed with status code {response.status_code}')
        time.sleep(15)
        ##bitbucket commit count 
        print(f"Target Repository - {repo_to_import} commit validation is in progress...")
        commits_url = f"https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_to_import}/commits/{default_branch}"
        commit_count = 0
        next_url = commits_url
        while next_url:
            response = requests.get(next_url,auth=auth)
            if response.status_code == 200:
                data = response.json()

                commits = data["values"]
                commit_count += len(commits)

                # Check if there are more pages
                if "next" in data:
                    next_url = data["next"]
                else:
                    next_url = None
            else:
                print(f"Error getting bitbucket commit count: {response.status_code} \n {response.text}")
        bitbucket_comit_count=commit_count
        print("")
        if bitbucket_branches==azure_branches :
            print("")
            print("Branch Validation Done")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_to_import} i.e {bitbucket_branches}")
            print("")
            print("")
        else:
            print("")
            print("Branch Validation Done")
            print(f"Branch Count are not same for both the repository {repo_to_import}.")
            print("")
            print("")
        if bitbucket_comit_count==azure_commit_count :
            print("")
            print("Commit Validation Done")
            print("")
            print(f"Commit Count are same for both the repository {repo_to_import} i.e {bitbucket_comit_count}.")
            print("")
            print("")
        else:
            print("")
            print("Commit Validation Done")
            print(f"Commit Count are not same for both the repository {repo_to_import}.")
            print("")
            print("")
        validation_data.append([azure_project_namespace,repo_to_import,bitbucket_workspace_id,azure_branches,bitbucket_branches,azure_commit_count,bitbucket_comit_count])
        
    else:
        error_message=f"Error occurred while pushing the mirror clone to Bitbucket repository {repo_to_import}. Return code: {push_process.returncode}"
        print(error_message)
        failure_data.append([repo_to_import, push_process.returncode, error_message])
        print("Error output:", push_process.stderr.decode())
        print("")
    

# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('success.csv', index_label='Sr')
# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('failure.csv', index_label='Sr')
# Create validation_data.csv
validation_df = pd.DataFrame(validation_data, columns=['Source Azure Project Namespace', 'Source Repository Name', 'Target BitBucket workspace id','Source Branches','Target Branches','Source Commits','Target Commits'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("New BitBucket Repository URLs")
for url in bitbucket_urls:
    print(url)
print("")
file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/azure-to-bitbucket/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")
for folder in clone:
    def rm_dir_readonly(func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)
    shutil.rmtree(folder, onerror=rm_dir_readonly)


    
