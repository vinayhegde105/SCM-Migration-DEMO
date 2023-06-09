import pandas as pd
import requests
import json
import time
from urllib.parse import quote
import os
# Read Excel file
df = pd.read_excel('./github-ado/github-to-azure.xlsx')

# print("")
# github_token = input("Enter the github access token: ")
# print("")
# azure_token = input("Enter the Azure devops access token: ")
# print("")
# gitlab_token = input("Enter the GitLab access token: ")
# print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
azure_token= os.getenv('AZURE_TOKEN')
github_token= os.getenv('GITHUB_TOKEN')
gitlab_token= os.getenv('GITLAB_TOKEN')
repo_path= os.getenv('GITLAB_LOG_PROJECT_PATH')

encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing GitHub to Azure Repos")
print("")
azure_urls = []
success_data = []
failure_data = []
validation_data=[]

for index, row in df.iterrows():
    sr = row['sr']
    github_username = row['github_username']
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
        print("")
    else:
        print(f"Error occurred while creating the repository {repo_name_to_import} with status code: {repo_response.status_code} \n {repo_response.text}")
        print("")
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
        failure_data.append([repo_name_to_import, response.status_code, error_message])

    org_url = f"https://dev.azure.com/{organization}/_apis/serviceendpoint/endpoints?api-version=7.0"
    payload = json.dumps({
    "authorization": {
        "scheme": "UsernamePassword",
        "parameters": {
        "username": github_username,
        "password": github_token
        }
    },
    "data": {},
    "description": "",
    "name": "GitHub",
    "serviceEndpointProjectReferences": [
        {
        "description": "",
        "name": "GitHub",
        "projectReference": {
            "id": project_id,
            "name": project
        }
        }
    ],
    "type": "git",
    "url": "https://github.com",
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
    # Import from GitHub
    data = {
        "parameters": {
            "gitSource": {
                "url": f"https://github.com/{github_username}/{repo_name_to_import}.git"
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
        print(f"Successfully imported {repo_name_to_import} from GitHub to Azure Repos.")
        success_data.append([repo_name_to_import, import_response.status_code])
        azure_urls.append(f'https://dev.azure.com/{azure_target_namespace}/_git/{repo_name_to_import}')
        time.sleep(30)
        #GitHub Branches Count
        print(f"Source Repository - {repo_name_to_import} branch validation is in progress...")
        per_page = 100
        url_1 = f'https://api.github.com/repos/{github_username}/{repo_name_to_import}/branches'
        headers_1 = {'Authorization': f'Bearer {github_token}'}

        total_branches = 0

        while url_1:
            response = requests.get(url_1, headers=headers_1, params={'per_page': per_page})
            if response.status_code == 200:
                branches = response.json()
                total_branches += len(branches)
                link_header = response.headers.get('Link')
                if link_header:
                    next_url = None
                    for link in link_header.split(','):
                        if 'rel="next"' in link:
                            next_url = link.split(';')[0][1:-1]
                    url_1 = next_url
                else:
                    url_1 = None
            else:
                print(f'Request failed with status code {response.status_code} \n {response.text}')
                break

        github_branches=total_branches

        ### GitHub Commit Count
        print(f"Source Repository - {repo_name_to_import} commit validation is in progress...")
        api_url = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}/commits"
        headers = {"Accept": "application/vnd.github.v3+json", 'Authorization': f'Bearer {github_token}'}
        params = {"per_page": 100} 

        commit_count = 0
        page = 1

        while True:
            response = requests.get(api_url, headers=headers, params=params)
            if response.status_code == 200:
                commits = response.json()
                commit_count += len(commits)
                
                if len(commits) == params["per_page"]:
                    page += 1
                    params["page"] = page
                else:
                    break 
            else:
                print(f"Error: {response.status_code} \n {response.text}")
                break
        github_comit_count=commit_count
                ##Github Repo Size
        url = f'https://api.github.com/repos/{github_username}/{repo_name_to_import}'
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            repo_size = response.json()['size']
            repo_size = repo_size/1024 
            github_size= f'{repo_size:.2f} MB'
        else:
            print(f'Error fetching github repository information: {response.status_code} {response.text}')
        ##Azure Branch Count
        print(f"Target Repository - {repo_name_to_import} branch validation is in progress...")
        url = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}"
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            repo_info = response.json()
            default_branch = repo_info['default_branch']
        else:
            print(f"Error getting default branch name: {response.status_code} - {response.text}")
        url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{repo_name_to_import}/refs?filter=heads/&api-version=7.0'
        params = {'searchCriteria.itemVersion.versionType': 'branch', 'searchCriteria.itemVersion.version': f'{default_branch}'}
        response = requests.get(url, auth=("", azure_token),params=params)

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
        ## Azure Repos Size
        api_url = f'https://dev.azure.com/{azure_target_namespace}/_apis/git/repositories/{repo_name_to_import}?api-version=7.0'
        response = requests.get(api_url, auth=("", azure_token))
        if response.status_code == 200:
            size_in_bytes = response.json()["size"]
            size_in_mb = size_in_bytes / (1024*1024)
            azure_size= f'{size_in_mb:.2f} MB'
        else:
            print(f'Error fetching Azure repository information: {response.status_code} {response.text}')
        if azure_branches==github_branches :
            print("")
            print("********************Branch Validation Done********************")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {azure_branches}")
            print("")
            print("")
        else:
            print("")
            print("********************Branch Validation Done********************")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if azure_commit_count==github_comit_count :
            print("")
            print("********************Commit Validation Done********************")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {azure_commit_count}.")
            print("")
            print("")
        else:
            print("")
            print("********************Commit Validation Done********************")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([github_username,repo_name_to_import,azure_target_namespace,github_branches,azure_branches,github_comit_count,azure_commit_count,github_size,azure_size])
    else:
        error_message= f"Error occurred while importing {repo_name_to_import} from GitHub to Azure Repos with status code: {import_response.status_code} \n {import_response.text}"
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
validation_df = pd.DataFrame(validation_data, columns=['Source GitHub Username', 'Source Github repo Name', 'Target Azure Namespace','Source Branches','Target Branches','Source Commits','Target Commits','Source Repo Size','Target Repo Size'])
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
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-azure/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")
