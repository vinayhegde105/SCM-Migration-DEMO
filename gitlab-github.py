import pandas as pd
import json
import requests
import time
from urllib.parse import quote
import base64
import os

# Read Excel file
df = pd.read_excel('./gitlab-to-github.xlsx')
print("")
github_token = os.getenv('GITHUB_TOKEN')
gitlab_token = os.getenv('GITLAB_TOKEN')
print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')
encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing GitLab to GitHub")
print("")
github_urls = []
success_data = []
failure_data = []
validation_data =[]

for index, row in df.iterrows():
    sr = row['sr']
    gitlab_project_namespace = row['gitlab_project_namespace']
    project_to_import = row['project_to_import']
    github_username = row['github_username']

    data = {
        "vcs": "git",
        "vcs_url": f"https://gitlab.com/{gitlab_project_namespace}/{project_to_import}.git"
    }
    repo_data = {
        "name": project_to_import,
        "private": False,
    }

    action_disable_data = {
        "enabled": False
    }
    gitlab_json_data = json.dumps(data)
    repo_json_data = json.dumps(repo_data)
    action_disable_data_json_data = json.dumps(action_disable_data)

    repo_endpoint = 'https://api.github.com/user/repos'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github+json'
    }
    repo_response = requests.post(repo_endpoint, headers=headers, data=repo_json_data)
    if repo_response.status_code == 201:
        print(f"Successfully created repository {project_to_import} on GitHub.")
    else:
        error_message=f"Error occurred while creating the repository {project_to_import} with status code: {repo_response.status_code} \n {repo_response.text}"
        print(error_message)
        failure_data.append([project_to_import, repo_response.status_code, error_message])
        continue
    # repo_response.raise_for_status()

    disable_action_endpoint = f'https://api.github.com/repos/{github_username}/{project_to_import}/actions/permissions'
    disable_action_response = requests.put(disable_action_endpoint, headers=headers, data=action_disable_data_json_data)
    if disable_action_response.status_code == 204:
        print(f"Successfully disabled actions for the repository {project_to_import}.")
    else:
        error_message=f"Error occurred while disabling actions for the repository {project_to_import} with status code: {disable_action_response.status_code} \n {disable_action_response.text}"
        print(error_message)
        failure_data.append([project_to_import, disable_action_response.status_code, error_message])
        continue
    # disable_action_response.raise_for_status()

    import_endpoint = f'https://api.github.com/repos/{github_username}/{project_to_import}/import'
    import_response = requests.put(import_endpoint, headers=headers, data=gitlab_json_data)
    if import_response.status_code == 201:
        print(f"Successfully imported {project_to_import} from GitLab to GitHub.")
        success_data.append([project_to_import, import_response.status_code])
        github_urls.append(f'https://github.com/{github_username}/{project_to_import}')
        time.sleep(15)
        print()
        print("")
        ## Gitlab Branches Count
        print(f"Source Repository - {project_to_import} branch validation is in progress...")
        path=f"{gitlab_project_namespace}/{project_to_import}"
        encoded_path= quote(path,safe='')
        url_2 = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/branches?per_page=1'

        response = requests.get(url_2)

        if response.status_code == 200:
            total_branches_2 = int(response.headers.get('X-Total'))
        else:
            print(f'Request failed with status code {response.status_code} \n {response.text}')
        gitlab_branches=total_branches_2

        ##GitLab Commit Count
        print(f"Source Repository - {project_to_import} commit validation is in progress...")
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}/repository/commits"
        params = {"per_page": 100} 

        commit_count = 0
        page = 1

        while True:
            params["page"] = page
            response = requests.get(api_url, params=params)
            
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
       #GitHub Branches Count
        print(f"Target Repository - {project_to_import} branch validation is in progress...")
        per_page = 100
        url_1 = f'https://api.github.com/repos/{github_username}/{project_to_import}/branches'
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
        time.sleep(15)
        ### GitHub Commit Count
        print(f"Target Repository - {project_to_import} commit validation is in progress...")
        api_url = f"https://api.github.com/repos/{github_username}/{project_to_import}/commits"
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
        print("")
        print("")
        if github_branches==gitlab_branches :
            print("")
            print("Branch Validation Done")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {project_to_import} i.e {github_branches}")
            print("")
            print("")
        else:
            print("")
            print("Branch Validation Done")
            print(f"Branch Count are not same for both the repository {project_to_import}.")
            print("")
            print("")
        if github_comit_count==gitlab_commit_count :
            print("")
            print("Commit Validation Done")
            print("")
            print(f"Commit Count are same for both the repository {project_to_import} i.e {github_comit_count}.")
            print("")
            print("")
        else:
            print("")
            print("Commit Validation Done")
            print(f"Commit Count are not same for both the repository {project_to_import}.")
            print("")
            print("")
        validation_data.append([gitlab_project_namespace,project_to_import,github_username,gitlab_branches,github_branches,gitlab_commit_count,github_comit_count])
    else:
        error_message=f"Error occurred while importing {project_to_import} from GitLab to GitHub with status code: {import_response.status_code} \n {import_response.text}"
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
validation_df = pd.DataFrame(validation_data, columns=['Source GitLab Namespace', 'Source GitLab Project Name', 'Target GitHub Username','Source Branches','Target Branches','Source Commits','Target Commits'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("")
print("")
print("New GitHub Repository URLs")
for url in github_urls:
    print(url)
print("")
file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/gitlab-to-github/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")
# file_path=['success.csv','failure.csv','validation-data.csv']
# print("")
# file_path = ['success.csv', 'failure.csv', 'validation-data.csv'] 
# for file in file_path:
#     with open(file, 'rb') as file_obj:
#         content = file_obj.read()
#         encoded_content = base64.b64encode(content).decode('utf-8')
#     api_url = f'https://api.github.com/repos/{github_username}/{log_repo_name}/contents/gitlab-to-github-logs/{file}'
#     headers = {
#         'Authorization': f'Token {github_token}',
#         'Accept': 'application/vnd.github.v3+json'
#     }
#     data = {
#         'message': f'Publishing {file}',
#         'content': encoded_content,
#     }
#     response = requests.put(api_url, headers=headers, json=data)
#     if response.status_code == 201:
#         print(f'File {file} published successfully in repository {log_repo_name}.')
#     else:
#         print(f'Failed to publish {file}. Error:', response.text)



