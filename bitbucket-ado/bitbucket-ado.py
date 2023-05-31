import pandas as pd
import requests
from urllib.parse import quote
import json
import time
import os

# Read Excel file
df = pd.read_excel('./bitbucket-ado/bitbucket-to-azure.xlsx')

# print("")
# azure_token = input("Enter the Azure devops access token: ")
# print("")
# bitbucket_username = input("Enter the Bitbucket usernme: ")
# print("")
# bitbucket_password = input("Enter the Bitbucket app password: ")
# print("")
# gitlab_token = input("Enter the GitLab access token: ")
# print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
bitbucket_username = os.getenv('BITBUCKET_USERNAME')
bitbucket_password = os.getenv('BITBUCKET_PASSWORD')
azure_token = os.getenv('AZURE_TOKEN')
gitlab_token =os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')

encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing BitBucket to Azure Repos")
print("")
azure_urls = []
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    workspace_id = row['workspace_id']
    repo_name_to_import = row['repo_name_to_import']
    azure_target_namespace = row['azure_target_namespace']


# Create Azure DevOps repository
    repo_data = {
        "name": repo_name_to_import
    }
    repo_url = f"https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories?api-version=7.0"
    repo_headers = {
        "Content-Type": "application/json"
    }
    repo_response = requests.post(repo_url, auth=("", azure_token), headers=repo_headers, json=repo_data)
    if repo_response.status_code == 201:
        print(f"Successfully created repository {repo_name_to_import} on Azure Devops.")
    else:
        error_message=f"Error occurred while creating the repository {repo_name_to_import} with status code: {repo_response.status_code} \n {repo_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, repo_response.status_code, error_message])
    repo_response.raise_for_status()
    organization = azure_target_namespace.split('/')[0]
    project = azure_target_namespace.split('/')[1]

    project_url =f"https://dev.azure.com/{organization}/_apis/projects/{project}?api-version=7.0"
    response = requests.request("GET", project_url, auth=("", azure_token))
    if response.status_code == 200:
        project_id = response.json()['id']
    else:
        error_message =f"Error occurred while getting the project id of {project} with status code: {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
        continue

    org_url = f"https://dev.azure.com/{organization}/_apis/serviceendpoint/endpoints?api-version=7.0"
    payload = json.dumps({
    "authorization": {
        "scheme": "UsernamePassword",
        "parameters": {
        "username": bitbucket_username,
        "password": bitbucket_password
        }
    },
    "data": {},
    "description": "",
    "name": "BitBucket",
    "serviceEndpointProjectReferences": [
        {
        "description": "",
        "name": "BitBucket",
        "projectReference": {
            "id": project_id,
            "name": project
        }
        }
    ],
    "type": "git",
    "url": "https://bitbucket.org",
    "isShared": False
    })
    headers = {
    'Content-Type': 'application/json'
    }
    response = requests.request("POST", org_url,auth=("", azure_token),headers=headers, data=payload)
    if response.status_code == 200:
        endpoint_id = response.json()['id']
    else:
        error_message =f"Error occurred while creating service endpoint with status code: {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
        continue
    # Import from Bitbucket
    data = {
        "parameters": {
            "gitSource": {
                "url": f"https://bitbucket.org/{workspace_id}/{repo_name_to_import}.git"
            },
        "serviceEndpointId": endpoint_id,
        "deleteServiceEndpointAfterImportIsDone": True
        }
    }
    import_url = f"https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{repo_name_to_import}/importRequests?api-version=7.0"
    import_headers = {
        "Content-Type": "application/json"
    }
    import_response = requests.post(import_url, auth=("", azure_token), headers=import_headers, json=data)
    if import_response.status_code == 201:
        print(f"Successfully imported {repo_name_to_import} from BitBucket to Azure Repos.")
        success_data.append([repo_name_to_import, import_response.status_code])
        azure_urls.append(f'https://dev.azure.com/{azure_target_namespace}/_git/{repo_name_to_import}')
        time.sleep(15)
        ##bitbucket branch count
        print(f"Source Repository - {repo_name_to_import} branch validation is in progress...")
        auth=(bitbucket_username,bitbucket_password)
        url = f'https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}/refs/branches?pagelen=100'
        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            branch_data = response.json()
            total_branches = branch_data['size']
            bitbucket_branches=total_branches
        else:
            print(f'Request failed with status code {response.status_code}')
        ##bitbucket commit count 
        url = f'https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}'
        response = requests.get(url,auth=auth)
        if response.status_code == 200:
            repo_data = response.json()
            default_branch = repo_data['mainbranch']['name']
        else:
            print(f"Failed to retrieve bitbucket repository default branch information. Status code: {response.status_code}")

        print(f"Source Repository - {repo_name_to_import} commit validation is in progress...")
        commits_url = f"https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}/commits/{default_branch}"
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
        
        ##Azure Branch Count
        print(f"Target Repository - {repo_name_to_import} branch validation is in progress...")
        url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{repo_name_to_import}/refs?filter=heads/&api-version=7.0'

        response = requests.get(url, auth=("", azure_token))

        if response.status_code == 200:
            branch_data = response.json()
            branch_count = len(branch_data['value'])
            azure_branches=branch_count
        else:
            print(f'Request failed with status code {response.status_code}')
        time.sleep(15)
        ## Azure Commit Count
        print(f"Target Repository - {repo_name_to_import} commit validation is in progress...")
        url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{repo_name_to_import}/commits?api-version=7.0'

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
        print("")
        print("")
        if azure_branches==bitbucket_branches :
            print("")
            print("Branch Validation Done")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {azure_branches}")
            print("")
            print("")
        else:
            print("")
            print("Branch Validation Done")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if azure_commit_count==bitbucket_comit_count :
            print("")
            print("Commit Validation Done")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {azure_commit_count}.")
            print("")
            print("")
        else:
            print("")
            print("Commit Validation Done")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([workspace_id,repo_name_to_import,azure_target_namespace,bitbucket_branches,azure_branches,bitbucket_comit_count,azure_commit_count])
    else:
        error_message=f"Error occurred while importing {repo_name_to_import} from BitBucket to Azure Repos with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, import_response.status_code, error_message])
    # import_response.raise_for_status()

# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('success.csv', index_label='Sr')
# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('failure.csv', index_label='Sr')
# Create validation_data.csv
validation_df = pd.DataFrame(validation_data, columns=['Source BitBucket Workspace ID', 'Source BitBucket Repository Name', 'Target Azure Namespace','Source Branches','Target Branches','Source Commits','Target Commits'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("")
print("New Azure Repositories URL")
for url in azure_urls:
    print(url)
print("")
file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/bitbucket-to-azure/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")