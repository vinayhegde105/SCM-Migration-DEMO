import pandas as pd
import time
import requests
from urllib.parse import quote  
import os    

# Read Excel file
df = pd.read_excel('./github-to-gitlab.xlsx')


# github_token = os.getenv('GITHUB_TOKEN')
# gitlab_token = os.getenv('GITLAB_TOKEN')
github_token = "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"
gitlab_token = "glpat-bE-ovizYnaJFeYspkcDK"
# print("")
# github_token = input("Enter the GitHub access token: ")
# print("")
# gitlab_token = input("Enter the GitLab access token: ")
print("")
print("Importing GitHub to GitLab")
print("")
gitlab_urls = []
# gitlab_access_token = 'glpat-bE-ovizYnaJFeYspkcDK'
# github_access_token = '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' vs8950---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
for index, row in df.iterrows():
    sr = row['sr']
    github_username = row['github_username']
    repo_name_to_import = row['repo_name_to_import']
    gitlab_target_namespace = row['gitlab_target_namespace']

    repo_id_endpoint = f"https://api.github.com/repos/{github_username}/{repo_name_to_import}"
    print(repo_id_endpoint)
    repo_id_headers = {
        'Authorization': f'token {github_token}'
    }
    repo_id_response = requests.get(repo_id_endpoint, headers=repo_id_headers)
    if repo_id_response.status_code == 200:
        repo_id = repo_id_response.json()['id']
    else:
        print(f"Error occurred while getting the repository id of {repo_name_to_import} with status code: {repo_id_response.status_code} \n {repo_id_response.text}")
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
        print(f"Error occurred while importing {repo_name_to_import} from GitHub to GitLab with status code: {import_response.status_code} \n {import_response.text}")
    # import_response.raise_for_status()

print("")
print("")
print("New GitLab Repositories URL")
for url in gitlab_urls:
    print(url)
