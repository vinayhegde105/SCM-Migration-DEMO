import pandas as pd
import json
import requests
import time
from urllib.parse import quote
import os
# Read Excel file
df = pd.read_excel('./bitbucket-github/bitbucket-to-github.xlsx')

print("")
# github_token = input("Enter the GitHub access token: ")
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
github_token = os.getenv('GITHUB_TOKEN')
gitlab_token =os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')

encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing BitBucket to GitHub")
print("")
github_urls = []
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    workspace_id = row['workspace_id']
    repo_name_to_import = row['repo_name_to_import']
    github_username = row['github_username']

    api_url = f"https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}"
    response = requests.get(api_url,auth=(bitbucket_username, bitbucket_password))
    if response.status_code==200:
        project_data = response.json()
        visibility = project_data.get('is_private')
    else:
        print("Error occurred while fetching repository details")

    data = {
        "vcs": "git",
        "vcs_url": f"https://{bitbucket_username}:{bitbucket_password}@bitbucket.org/{workspace_id}/{repo_name_to_import}.git"
    }
    repo_data = {
        "name": repo_name_to_import,
        "private": True if visibility==True else False,
    }

    action_disable_data = {
        "enabled": False
    }
    bitbucket_json_data = json.dumps(data)
    repo_json_data = json.dumps(repo_data)
    action_disable_data_json_data = json.dumps(action_disable_data)

    repo_endpoint = 'https://api.github.com/user/repos'
    headers = {
        'Authorization': f'token {github_token}',
        'Accept': 'application/vnd.github+json'
    }
    repo_response = requests.post(repo_endpoint, headers=headers, data=repo_json_data)
    if repo_response.status_code == 201:
        print(f"Successfully created repository {repo_name_to_import} on GitHub.")
    else:
        error_message=f"Error occurred while creating the repository {repo_name_to_import} with status code: {repo_response.status_code} \n {repo_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, repo_response.status_code, error_message])
        continue
    # repo_response.raise_for_status()

    disable_action_endpoint = f'https://api.github.com/repos/{github_username}/{repo_name_to_import}/actions/permissions'
    disable_action_response = requests.put(disable_action_endpoint, headers=headers, data=action_disable_data_json_data)
    if disable_action_response.status_code == 204:
        print(f"Successfully disabled actions for the repository {repo_name_to_import}.")
    else:
        error_message=f"Error occurred while disabling actions for the repository {repo_name_to_import} with status code: {disable_action_response.status_code} \n {disable_action_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, disable_action_response.status_code, error_message])
#     disable_action_response.raise_for_status()

    import_endpoint = f'https://api.github.com/repos/{github_username}/{repo_name_to_import}/import'
    import_response = requests.put(import_endpoint, headers=headers, data=bitbucket_json_data)
    if import_response.status_code == 201:
        print(f"Successfully imported {repo_name_to_import} from BitBucket to GitHub.")
        success_data.append([repo_name_to_import, import_response.status_code])
        github_urls.append(f'https://github.com/{github_username}/{repo_name_to_import}')
        time.sleep(30)
        print()
        print("")
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
        ## Bitbucket Repo Size
        api_url = f'https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}'
        response = requests.get(api_url, auth=auth)
        if response.status_code == 200:
            repository_size_bytes = response.json()["size"]
            repository_size_mb = repository_size_bytes / (1024 * 1024)
            bitbucket_size=f'{repository_size_mb:.2f} MB'
        else: 
            print(f'Error fetching Bitbucket repository information: {response.status_code} {response.text}')
        #GitHub Branches Count
        print(f"Target Repository - {repo_name_to_import} branch validation is in progress...")
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
        time.sleep(15)
        ### GitHub Commit Count
        print(f"Target Repository - {repo_name_to_import} commit validation is in progress...")
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
        print("")
        print("")
        if github_branches==bitbucket_branches :
            print("")
            print("********************Branch Validation Done********************")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {github_branches}")
            print("")
            print("")
        else:
            print("")
            print("********************Branch Validation Done********************")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if github_comit_count==bitbucket_comit_count :
            print("")
            print("********************Commit Validation Done********************")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {github_comit_count}.")
            print("")
            print("")
        else:
            print("")
            print("********************Commit Validation Done********************")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([workspace_id,repo_name_to_import,github_username,bitbucket_branches,github_branches,bitbucket_comit_count,github_comit_count,bitbucket_size,github_size])
    else:
        error_message=f"Error occurred while importing {repo_name_to_import} from BitBucket to GitHub with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, import_response.status_code, error_message])
#     import_response.raise_for_status()
# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('success.csv', index_label='Sr')
# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('failure.csv', index_label='Sr')
# Create validation_data.csv
validation_df = pd.DataFrame(validation_data, columns=['Source BitBucket workspace id', 'Source BitBucket Repository Name', 'Target GitHub Username','Source Branches','Target Branches','Source Commits','Target Commits','Source Repo Size','Target Repo Size'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("")
print("New GitHub Repository URL")
for url in github_urls:
    print(url)
print("")
file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/bitbucket-to-github/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")