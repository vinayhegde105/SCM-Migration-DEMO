import pandas as pd
import requests
import subprocess
from urllib.parse import quote
import time
import shutil
import os
import stat

# Read Excel file
df = pd.read_excel('./github-bitbucket/github-to-bitbucket.xlsx')

# print("")
# bitbucket_username = input("Enter the Bitbucket usernme: ")
# print("")
# bitbucket_password = input("Enter the Bitbucket app password: ")
# print("")
# github_token = input("Enter the GitHub access token: ")
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
print("Importing GitHub to BitBucket")
print("")
bitbucket_urls = []
clone=[]
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    github_username = row['github_username']
    repo_name_to_import = row['repo_name_to_import']
    bitbucket_workspace_id = row['bitbucket_workspace_id']
    bitbucket_project_key = row['bitbucket_project_key']

    
    api_url = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}"
    headers = {
        'Authorization': f'token {github_token}'
    }
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        repo_data = response.json()
        visibility = repo_data['private']
    else:
        error_message="Error occurred while fetching project visibility details"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
    repo_data = {
        "scm": "git",
        "is_private": True if visibility == True else False,
        "project": {
            "key": f"{bitbucket_project_key}"
        }
    }
    api = f"https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_name_to_import.lower()}"
    headers = {
        'Content-Type': 'application/json',
    }
    auth=(bitbucket_username,bitbucket_password)
    response = requests.post(api, json=repo_data, headers=headers,auth=auth)
    if response.status_code == 200:
        print(f"Successfully created repository {repo_name_to_import} on BitBucket.")
        time.sleep(5)
    else:
        error_message = f"Error occurred while creating the repository {repo_name_to_import} with status code: {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
        print("")
    print("")
    clone_url = f"https://{github_token}@github.com/{github_username}/{repo_name_to_import}.git"
    mirror_clone_path = f"./{repo_name_to_import}"
    clone_process = subprocess.run(["git", "clone", "--mirror", clone_url, mirror_clone_path], capture_output=True)
    if clone_process.returncode == 0:
        print(f"Mirror clone created successfully for {repo_name_to_import}.")
        clone.append(repo_name_to_import)
        print("")
    else:
        error_message=f"Error occurred while creating the mirror clone for {repo_name_to_import}. Return code: {clone_process.returncode}"
        print(error_message)
        failure_data.append([repo_name_to_import, clone_process.returncode, error_message])
        print("Error output:", clone_process.stderr.decode())
        print("")

    push_url = f"https://{bitbucket_username}:{bitbucket_password}@bitbucket.org/{bitbucket_workspace_id}/{repo_name_to_import}.git"
    push_process = subprocess.run(["git", "push", "--mirror", push_url], cwd=mirror_clone_path, capture_output=True)
    if push_process.returncode == 0:
        print(f"Mirror clone pushed to Bitbucket repository {repo_name_to_import} successfully.")
        bitbucket_urls.append(f'https://bitbucket.org/{bitbucket_workspace_id}/{repo_name_to_import}.git')
        success_data.append([repo_name_to_import, push_process.returncode])
        time.sleep(15)
        print("")
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
        ##bitbucket branch count
        print(f"Target Repository - {repo_name_to_import} branch validation is in progress...")
        auth=(bitbucket_username,bitbucket_password)
        url = f'https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_name_to_import}/refs/branches?pagelen=100'
        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            branch_data = response.json()
            total_branches = branch_data['size']
            bitbucket_branches=total_branches
        else:
            print(f'Request failed with status code {response.status_code}')
        time.sleep(15)
        ##bitbucket commit count 
        url = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}"
        headers = {"Accept": "application/vnd.github.v3+json", 'Authorization': f'Bearer {github_token}'}
        response = requests.get(url,headers=headers)
        if response.status_code == 200:
            repo_info = response.json()
            default_branch = repo_info['default_branch']
        else:
            print(f"Error getting default branch name: {response.status_code} - {response.text}")
        print(f"Target Repository - {repo_name_to_import} commit validation is in progress...")
        commits_url = f"https://api.bitbucket.org/2.0/repositories/{bitbucket_workspace_id}/{repo_name_to_import}/commits/{default_branch}"
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
        if bitbucket_branches==github_branches :
            print("")
            print("********************Branch Validation Done********************")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {bitbucket_branches}")
            print("")
            print("")
        else:
            print("")
            print("********************Branch Validation Done********************")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if bitbucket_comit_count==github_comit_count :
            print("")
            print("********************Commit Validation Done********************")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {bitbucket_comit_count}.")
            print("")
            print("")
        else:
            print("")
            print("********************Commit Validation Done********************")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([github_username,repo_name_to_import,bitbucket_workspace_id,github_branches,bitbucket_branches,github_comit_count,bitbucket_comit_count])
        
    else:
        error_message=f"Error occurred while pushing the mirror clone to Bitbucket repository {repo_name_to_import}. Return code: {push_process.returncode}"
        print(error_message)
        failure_data.append([repo_name_to_import, push_process.returncode, error_message])
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
validation_df = pd.DataFrame(validation_data, columns=['Source GitHub Username', 'Source Repository Name', 'Target BitBucket workspace id','Source Branches','Target Branches','Source Commits','Target Commits'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("New BitBucket Repository URLs")
for url in bitbucket_urls:
    print(url)
print("")
file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-bitbucket/0.0.1/{file}"
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


    
