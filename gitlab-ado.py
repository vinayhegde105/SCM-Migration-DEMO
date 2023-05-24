import pandas as pd
import requests
from urllib.parse import quote
import time
import base64
import os
import json


# Read Excel file
df = pd.read_excel('./gitlab-to-azure.xlsx')
print("")
azure_token = os.getenv('AZURE_TOKEN')
gitlab_token = os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')
print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
encoded_repo_path= quote(repo_path,safe='')
print("Importing GitLab to Azure Repos")
print("")
azure_urls = []
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    gitlab_project_namespace = row['gitlab_project_namespace']
    project_to_import = row['project_to_import']
    azure_target_namespace = row['azure_target_namespace']


# Create Azure DevOps repository
    repo_data = {
        "name": project_to_import
    }
    repo_url = f"https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories?api-version=7.0"
    repo_headers = {
        "Content-Type": "application/json"
    }
    repo_response = requests.post(repo_url, auth=("", azure_token), headers=repo_headers, json=repo_data)
    if repo_response.status_code == 201:
        print(f"Successfully created repository {project_to_import} on Azure Devops.")
    else:
        error_message=f"Error occurred while creating the repository {project_to_import} with status code: {repo_response.status_code} \n {repo_response.text}"
        print(error_message)
        failure_data.append([project_to_import, repo_response.status_code, error_message])
    # repo_response.raise_for_status()
    organization = azure_target_namespace.split('/')[0]
    project = azure_target_namespace.split('/')[1]

    project_url =f"https://dev.azure.com/{organization}/_apis/projects/{project}?api-version=7.0"
    response = requests.request("GET", project_url, auth=("", azure_token))
    if response.status_code == 200:
        project_id = response.json()['id']
    else:
        error_message =f"Error occurred while getting the project id of {project} with status code: {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([project_to_import, response.status_code, error_message])

    org_url = f"https://dev.azure.com/{organization}/_apis/serviceendpoint/endpoints?api-version=7.0"
    payload = json.dumps({
    "authorization": {
        "scheme": "UsernamePassword",
        "parameters": {
        "username": "",
        "password": gitlab_token
        }
    },
    "data": {},
    "description": "",
    "name": "GitLab",
    "serviceEndpointProjectReferences": [
        {
        "description": "",
        "name": "GitLab",
        "projectReference": {
            "id": project_id,
            "name": project
        }
        }
    ],
    "type": "git",
    "url": "https://gitlab.com",
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
        failure_data.append([project_to_import, response.status_code, error_message])
    # Import from GitLab
    data = {
        "parameters": {
            "gitSource": {
                "url": f"https://gitlab.com/{gitlab_project_namespace}/{project_to_import}.git"
            },
        "serviceEndpointId": endpoint_id,
        "deleteServiceEndpointAfterImportIsDone": True
        }
    }
    import_url = f"https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{project_to_import}/importRequests?api-version=7.0"
    import_headers = {
        "Content-Type": "application/json"
    }
    import_response = requests.post(import_url, auth=("", azure_token), headers=import_headers, json=data)
    if import_response.status_code == 201:
        print(f"Successfully imported {project_to_import} from GitLab to Azure Repos.")
        success_data.append([project_to_import, import_response.status_code])
        print("")
        azure_urls.append(f'https://dev.azure.com/{azure_target_namespace}/_git/{project_to_import}')
        time.sleep(15)
        ## Gitlab Branches Count
        print(f"Source Repository - {project_to_import} branch validation is in progress...")
        path=f"{gitlab_project_namespace}/{project_to_import}"
        encoded_path= quote(path,safe='')
        url_2 = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/branches?per_page=1'
        headers = {
        'PRIVATE-TOKEN': gitlab_token
        }
        response = requests.get(url_2,headers=headers)

        if response.status_code == 200:
            total_branches_2 = int(response.headers.get('X-Total'))
            gitlab_branches=total_branches_2
        else:
            print(f'Request failed with status code {response.status_code} \n {response.text}')

        ##GitLab Commit Count
        print(f"Source Repository - {project_to_import} commit validation is in progress...")
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}/repository/commits"
        params = {"per_page": 100} 

        commit_count = 0
        page = 1

        while True:
            params["page"] = page
            response = requests.get(api_url,headers=headers,params=params)
            
            if response.status_code == 200:
                commits = response.json()
                commit_count += len(commits)
                
                if len(commits) == params["per_page"]:
                    page += 1
                else:
                    break 
            else:
                print(f"Error: {response.status_code} \n {response.text}")
                break
        gitlab_commit_count=commit_count
        ##Azure Branch Count
        print(f"Target Repository - {project_to_import} branch validation is in progress...")
        url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{project_to_import}/refs?filter=heads/&api-version=7.0'

        response = requests.get(url, auth=("", azure_token))

        if response.status_code == 200:
            branch_data = response.json()
            branch_count = len(branch_data['value'])
            azure_branches=branch_count
        else:
            print(f'Request failed with status code {response.status_code}')
        time.sleep(15)
        ## Azure Commit Count
        print(f"Target Repository - {project_to_import} commit validation is in progress...")
        path=f"{gitlab_project_namespace}/{project_to_import}"
        encoded_path= quote(path,safe='')
        url = f'https://gitlab.com/api/v4/projects/{encoded_path}'
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            project_info = response.json()
            default_branch = project_info['default_branch']
        else:
            print(f"Error getting default branch name: {response.status_code} - {response.text}")
        url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{project_to_import}/commits?api-version=7.0'

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
        if azure_branches==gitlab_branches :
            print("")
            print("Branch Validation Done")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {project_to_import} i.e {azure_branches}")
            print("")
            print("")
        else:
            print("")
            print("Branch Validation Done")
            print(f"Branch Count are not same for both the repository {project_to_import}.")
            print("")
            print("")
        if azure_commit_count==gitlab_commit_count :
            print("")
            print("Commit Validation Done")
            print("")
            print(f"Commit Count are same for both the repository {project_to_import} i.e {azure_commit_count}.")
            print("")
            print("")
        else:
            print("")
            print("Commit Validation Done")
            print(f"Commit Count are not same for both the repository {project_to_import}.")
            print("")
            print("")
        validation_data.append([gitlab_project_namespace,project_to_import,azure_target_namespace,gitlab_branches,azure_branches,gitlab_commit_count,azure_commit_count])
    else:
        error_message=f"Error occurred while importing {project_to_import} from GitLab to Azure Repos with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([project_to_import, import_response.status_code, error_message])
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
validation_df = pd.DataFrame(validation_data, columns=['Source GitLab Namespace', 'Source GitLab Project Name', 'Target Azure Namespace','Source Branches','Target Branches','Source Commits','Target Commits'])
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
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/gitlab-to-azure/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")

