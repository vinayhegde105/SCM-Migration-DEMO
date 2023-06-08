import requests
import json
import pandas as pd
import time
from urllib.parse import quote
import os

# Read Excel file
df = pd.read_excel('./bitbucket-gitlab/bitbucket-to-gitlab.xlsx')

# print("")
# bitbucket_username = input("Enter the Bitbucket usernme: ")
# print("")
# bitbucket_password = input("Enter the Bitbucket app password: ")
# print("")
# gitlab_token = input("Enter the Gitlab access token: ")
# print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
bitbucket_username = os.getenv('BITBUCKET_USERNAME')
bitbucket_password = os.getenv('BITBUCKET_PASSWORD')
gitlab_token =os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')

encoded_repo_path= quote(repo_path,safe='')
print("")
print("")
print("Importing BitBucket to GitLab")
print("")
gitlab_urls=[]
success_data = []
failure_data = []
validation_data=[]
for index, row in df.iterrows():
    sr = row['sr']
    workspace_id = row['workspace_id']
    repo_name_to_import = row['repo_name_to_import']
    gitlab_target_namespace = row['gitlab_target_namespace']
    
    encoded_path= quote(gitlab_target_namespace,safe='')
    api_url = f'https://gitlab.com/api/v4/groups/{encoded_path}'
    headers = {'PRIVATE-TOKEN': gitlab_token}

    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        group_data = response.json()
        group_id = group_data['id']
    else:
        error_message=f"Failed to retrieve group id with status code {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
    api_url = f"https://api.bitbucket.org/2.0/repositories/{workspace_id}/{repo_name_to_import}"
    response = requests.get(api_url,auth=(bitbucket_username, bitbucket_password))
    if response.status_code==200:
        project_data = response.json()
        visibility = project_data.get('is_private')
    else:
        error_message=f"Error occurred while fetching repository visibility details with status code {response.status_code} \n {response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, response.status_code, error_message])
    
    url = "https://gitlab.com/api/v4/projects/"
    payload = json.dumps({
    "name": repo_name_to_import,
    "namespace_id": group_id,
    "visibility": "private" if visibility==True else "public",
    "import_url": f"https://{bitbucket_username}:{bitbucket_password}@bitbucket.org/{workspace_id}/{repo_name_to_import}.git"
    })
    headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {gitlab_token}',
    }
    import_response = requests.request("POST", url, headers=headers, data=payload)
    if import_response.status_code==201:
        success_data.append([repo_name_to_import, import_response.status_code])
        print(f"Successfully imported {repo_name_to_import} from BitBucket to GitLab.")
        gitlab_urls.append(f'https://gitlab.com/{gitlab_target_namespace}/{repo_name_to_import}')
        print("")
        time.sleep(30)
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
        ## Gitlab Branches Count
        print(f"Target Repository - {repo_name_to_import} branch validation is in progress...")
        path=f"{gitlab_target_namespace}/{repo_name_to_import}"
        encoded_path= quote(path,safe='')
        url_2 = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/branches?per_page=1'
        headers_2 = {'PRIVATE-TOKEN': gitlab_token}

        response = requests.get(url_2, headers=headers_2)

        if response.status_code == 200:
            total_branches_2 = int(response.headers.get('X-Total'))
        else:
            print(f'Request failed with status code {response.status_code} \n {response.text}')
        gitlab_branches=total_branches_2
        time.sleep(15)

        ##GitLab Commit Count
        print(f"Target Repository - {repo_name_to_import} commit validation is in progress...")
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}/repository/commits"
        headers = {"Authorization": f"Bearer {gitlab_token}"}
        params = {"per_page": 100} 

        commit_count = 0
        page = 1

        while True:
            params["page"] = page
            response = requests.get(api_url, headers=headers, params=params)
            
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
        ##Gitlab Project Size
        api_url = f"https://gitlab.com/api/v4/projects/{encoded_path}?statistics=true"
        response = requests.get(api_url, headers=headers)
        response_json = response.json()

        if response.status_code == 200:
            repository_storage_bytes = response_json["statistics"]["storage_size"]
            repository_storage_mb = repository_storage_bytes / (1024 * 1024)
            gitlab_size= f'{repository_storage_mb:.2f} MB'
        else:
            print("Failed to fetch gitlab project size")
        print("")
        print("")
        if gitlab_branches==bitbucket_branches :
            print("")
            print("********************Branch Validation Done********************")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {gitlab_branches}")
            print("")
            print("")
        else:
            print("")
            print("********************Branch Validation Done********************")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if bitbucket_comit_count==gitlab_commit_count :
            print("")
            print("********************Commit Validation Done********************")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {gitlab_commit_count}.")
            print("")
            print("")
        else:
            print("")
            print("********************Commit Validation Done********************")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([workspace_id,repo_name_to_import,gitlab_target_namespace,bitbucket_branches,gitlab_branches,bitbucket_comit_count,gitlab_commit_count,bitbucket_size,gitlab_size])
    else:
        error_message=f"Error occurred while importing {repo_name_to_import} from BitBucket to GitLab with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, import_response.status_code, error_message])

# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('success.csv', index_label='Sr')

# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('failure.csv', index_label='Sr')
# Create validation_data.csv
validation_df = pd.DataFrame(validation_data, columns=['Source BitBucket workspace id', 'Source BitBucket Repository Name', 'Target Gitlab Namespace','Source Branches','Target Branches','Source Commits','Target Commits','Source Repo Size','Target Repo Size'])
validation_df.index =validation_df.index+1
validation_df.to_csv('validation-data.csv', index_label='Sr')
print("")
print("New GitLab Repositories URL")
for url in gitlab_urls:
    print(url)
print("")
print("")

file_path=['success.csv','failure.csv','validation-data.csv']
for file in file_path:
    package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/bitbucket-to-gitlab/0.0.1/{file}"
    headers = {'PRIVATE-TOKEN': gitlab_token}
    with open(file, 'rb') as file_obj:
        data = file_obj.read()
        response = requests.put(package_url_1, headers=headers, data=data)
    if response.status_code == 201:
        print(f"Published {file} file to Package Registry in GitLab")
    else:
        print(f"Error while publishing {file} to Package Registry with status code {response.status_code}\n{response.text}")