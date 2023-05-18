import pandas as pd
import time
import requests
from urllib.parse import quote

# Read Excel file
df = pd.read_excel('./github-to-gitlab.xlsx')

# print("")
# github_token = input("Enter the GitHub access token: ")
# print("")
# gitlab_token = input("Enter the GitLab access token: ")
# print("")
# repo_path = input("Enter the gitlab project path for storing the Migration Logs [gitlab_namespace/project_name]: ")
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
       #GitHub Branches Count
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
                print(f'Request failed with status code {response.status_code}')
                break

        github_branches=total_branches

        ## Gitlab Branches Count
        path=f"{gitlab_target_namespace}/{repo_name_to_import}"
        encoded_path= quote(path,safe='')
        url_2 = f'https://gitlab.com/api/v4/projects/{encoded_path}/repository/branches?per_page=1'
        headers_2 = {'PRIVATE-TOKEN': gitlab_token}

        response = requests.get(url_2, headers=headers_2)

        if response.status_code == 200:
            total_branches_2 = int(response.headers.get('X-Total'))
        else:
            print(f'Request failed with status code {response.status_code}')
        gitlab_branches=total_branches_2

        if github_branches==gitlab_branches :
            print(f"Branch Count are same for both the repository {repo_name_to_import}= {gitlab_branches}.")
            print("")
            print("")
        else:
            print(f"Branch Count are not same for both the repository {repo_name_to_import}.")
            print("")
            print("")

    else:
        error_message =f"Error occurred while importing {repo_name_to_import} from GitHub to GitLab with status code: {import_response.status_code} \n {import_response.text}"
        print(error_message)
        failure_data.append([repo_name_to_import, import_response.status_code, error_message])

    # import_response.raise_for_status()
# Create success.csv
success_df = pd.DataFrame(success_data, columns=['Repository Name', 'Status Code'])
success_df.index = success_df.index+1
success_df.to_csv('github-to-gitlab-success.csv')

# Create failure.csv
failure_df = pd.DataFrame(failure_data, columns=['Repository Name', 'Status Code', 'Error Message'])
failure_df.index =failure_df.index+1
failure_df.to_csv('github-to-gitlab-failure.csv')
print("")
print("")
print("New GitLab Repositories URL")
for url in gitlab_urls:
    print(url)
print("")
print("")
package_url_1 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-gitlab/0.0.1/success.csv"
success_files=[('',('github-to-gitlab-success.csv',open('github-to-gitlab-success.csv','rb'),'text/csv'))]
headers = {'PRIVATE-TOKEN': gitlab_token}
response_1 = requests.request("PUT", package_url_1, headers=headers, files=success_files)
if response_1.status_code ==201:
    print("Published success.csv file to Package Registry in GitLab ")
else:
    print (f"Error while publishing success.csv to Package Registry with status code {response_1.status_code} \n {response_1.text}")

package_url_2 = f"https://gitlab.com/api/v4/projects/{encoded_repo_path}/packages/generic/github-to-gitlab/0.0.1/failure.csv"
failure_files=[('',('github-to-gitlab-failure.csv',open('github-to-gitlab-failure.csv','rb'),'text/csv'))]
response_2 = requests.request("PUT", package_url_2, headers=headers, files=failure_files)
if response_2.status_code ==201:
    print("Published failure.csv file to Package Registry in GitLab ")
else:
    print (f"Error while publishing failure.csv to Package Registry with status code {response_2.status_code} \n {response_2.text}")


