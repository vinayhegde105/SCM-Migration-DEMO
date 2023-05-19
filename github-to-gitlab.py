import pandas as pd
import os
import time
import requests
from urllib.parse import quote

#Works only with Linux Flatform

# Read Excel file
df = pd.read_excel('./github-to-gitlab.xlsx')

github_token = os.getenv('GITHUB_TOKEN')
gitlab_token = os.getenv('GITLAB_TOKEN')
repo_path = os.getenv('GITLAB_LOG_PROJECT_PATH')
encoded_repo_path= quote(repo_path,safe='')
print("")
print("Importing GitHub to GitLab")
print("")
gitlab_urls = []
success_data = []
failure_data = []
validation_data=[]

for index, row in df.iterrows():
    sr = row['sr']
    github_username = row['github_username']
    repo_name_to_import = row['repo_name_to_import']
    gitlab_target_namespace = row['gitlab_target_namespace']

    repo_id_endpoint = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}"
    repo_id_headers = {
        'Authorization': f'token {github_token}'
    }
    repo_id_response = requests.get(repo_id_endpoint, headers=repo_id_headers)
    if repo_id_response.status_code == 200:
        repo_id = repo_id_response.json()['id']
    else:
        error_message =f"Error occurred while getting the repository id of {repo_name_to_import} with status code: {repo_id_response.status_code} \n {repo_id_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, repo_id_response.status_code, error_message])
        continue

    # repo_id_response.raise_for_status()

    import_endpoint = "https://gitlab.com/api/v4/import/github"
    import_params = {
        'personal_access_token': github_token,
        'repo_id': repo_id,
        'target_namespace': gitlab_target_namespace
    }
    import_headers = {
        'PRIVATE-TOKEN': gitlab_token
    }
    import_response = requests.post(import_endpoint, headers=import_headers, data=import_params)
    if import_response.status_code == 201:
        success_data.append([repo_name_to_import, import_response.status_code])
        print(f"Successfully imported {repo_name_to_import} from GitHub to GitLab.")
        gitlab_urls.append(f'https://gitlab.com/{gitlab_target_namespace}/{repo_name_to_import}')
        time.sleep(10)
        print()
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
        print("")
        print("")
        if github_branches==gitlab_branches :
            print("")
            print("Branch Validation Done")
            print("")
            print("")
            print(f"Branch counts are same for both the repository {repo_name_to_import} i.e {gitlab_branches}")
            print("")
            print("")
        else:
            print("")
            print("Branch Validation Done")
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        if github_comit_count==gitlab_commit_count :
            print("")
            print("Commit Validation Done")
            print("")
            print(f"Commit Count are same for both the repository {repo_name_to_import} i.e {gitlab_commit_count}.")
            print("")
            print("")
        else:
            print("")
            print("Commit Validation Done")
            print(f"Commit Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")
        validation_data.append([github_username,repo_name_to_import,gitlab_target_namespace,github_branches,github_comit_count,gitlab_branches,gitlab_commit_count])

    else:
        error_message =f"Error occurred while importing {repo_name_to_import} from GitHub to GitLab with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, import_response.status_code, error_message])

    # import_response.raise_for_status()
# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('github-to-gitlab-success.csv', index_label='Sr')

# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('github-to-gitlab-failure.csv', index_label='Sr')
# Create validation_data.csv
validation_df = pd.DataFrame(validation_data, columns=['Source Github Username', 'Source Github Repository Name', 'Target Gitlab Namespace','Source Branches','Source Commits','Target Branches','Target Commits'])
validation_df.index =validation_df.index+1
validation_df.to_csv('github-to-gitlab-validation.csv', index_label='Sr')
print("")
print("New GitLab Repositories URL")
for url in gitlab_urls:
    print(url)
print("")
print("")
package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-gitlab/0.0.1/success.csv"
headers = {'PRIVATE-TOKEN': gitlab_token}
with open('github-to-gitlab-success.csv', 'rb') as file:
    data = file.read()
    response_1 = requests.put(package_url_1, headers=headers, data=data)

if response_1.status_code == 201:
    print("Published success.csv file to Package Registry in GitLab")
else:
    print(f"Error while publishing success.csv to Package Registry with status code {response_1.status_code}\n{response_1.text}")


package_url_2 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-gitlab/0.0.1/failure.csv"
with open('github-to-gitlab-failure.csv', 'rb') as file:
    data = file.read()
    response_2 = requests.put(package_url_2, headers=headers, data=data)

if response_2.status_code == 201:
    print("Published failure.csv file to Package Registry in GitLab")
else:
    print(f"Error while publishing failure.csv to Package Registry with status code {response_2.status_code}\n{response_2.text}")

package_url_3 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-gitlab/0.0.1/validation-data.csv"
with open('github-to-gitlab-validation.csv', 'rb') as file:
    data = file.read()
    response_3 = requests.put(package_url_3, headers=headers, data=data)

if response_3.status_code == 201:
    print("Published validation-data.csv file to Package Registry in GitLab")
else:
    print(f"Error while publishing validation-data.csv to Package Registry with status code {response_3.status_code}\n{response_3.text}")
