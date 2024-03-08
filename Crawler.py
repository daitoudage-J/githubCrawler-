import requests
import pandas as pd
import base64
import time
from urllib.parse import quote_plus
from tqdm import tqdm
import certifi
import urllib3

# 禁用SSL验证
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def make_request(url):
    """Make a request with rate limit handling."""
    while True:
        try:
            response = requests.get(url, headers=headers, verify=False, proxies={})
            if response.status_code == 403 and 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                # We hit the rate limit, wait and try again
                reset_time = int(response.headers['X-RateLimit-Reset'])
                sleep_time = max(reset_time - time.time(), 0)
                print(f"Rate limit hit. Sleeping for {sleep_time} seconds.")
                time.sleep(sleep_time + 1)  # Adding 1 second just to be safe
            else:
                return response
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(5)  # Wait for some time before retrying

def fetch_all_repositories(search_url):
    """Fetch all repositories matching the search query."""
    repositories_urls = []
    while search_url:
        response = make_request(search_url)
        if response.status_code == 200:
            search_data = response.json()
            repositories_urls.extend([item['url'] for item in search_data['items']])
            search_url = response.links.get('next', {}).get('url', None)
        else:
            break
    return repositories_urls

def get_main_language(repo_url):
    """Get the main programming language of a repository."""
    languages_url = f"{repo_url}/languages"
    response = make_request(languages_url)
    if response.status_code == 200:
        languages_data = response.json()
        if languages_data:
            main_language = max(languages_data, key=languages_data.get)
            return main_language
    return 'Unknown'

# GitHub OAuth token
oauth_token = 'xxxxxxxxxx'#Replace xxxxxxxxxx with your github token
headers = {'Authorization': f'token {oauth_token}'}

# User input for the search query
user_input = input("Input retrieval formula: ")
search_query = quote_plus(user_input)
search_url = f"https://api.github.com/search/repositories?q={search_query}&sort=stars&order=desc"

repositories_urls = fetch_all_repositories(search_url)

# Initialize an empty list to store the data
data_list = []

# Loop through each repository URL and gather data with tqdm progress bar
for repo_url in tqdm(repositories_urls, desc="Processing Repositories"):
    # Fetch repository details
    repo_response = make_request(repo_url)
    repo_data = repo_response.json()

    # Extracting required information
    project_name = repo_data['name']
    owner_name = repo_data['owner']['login']
    owner_url = repo_data['owner']['url']
    created_at = repo_data['created_at']
    stars_count = repo_data['stargazers_count']
    forks_count = repo_data['forks_count']  # 获取fork数目
    watching_count = repo_data['subscribers_count']  # 使用subscribers_count字段获取watching数目
    about = repo_data['description']
    topics = repo_data.get('topics', [])

    # Fetch owner details for location
    owner_response = make_request(owner_url)
    owner_data = owner_response.json()
    location = owner_data.get('location', 'Not Specified')

    # Fetch the total number of commits
    commits_url = repo_data['commits_url'].split('{')[0] + '?per_page=1'
    commits_response = make_request(commits_url)
    if 'last' in commits_response.links:
        total_commits = commits_response.links['last']['url'].split('=')[-1]
    else:
        total_commits = 1 if commits_response.json() else 0

    # Fetch the latest commit
    latest_commit_url = repo_data['commits_url'].split('{')[0] + '?per_page=1'
    latest_commit_response = make_request(latest_commit_url)
    latest_commit_data = latest_commit_response.json()

    # Check if the response contains commit data
    if isinstance(latest_commit_data, list) and len(latest_commit_data) > 0:
        relative_time = latest_commit_data[0]['commit']['committer']['date']
    else:
        relative_time = None

    # Fetch the README
    readme_url = repo_data['contents_url'].replace('{+path}', 'README.md')
    readme_response = make_request(readme_url)
    readme_data = readme_response.json()
    readme_content = base64.b64decode(readme_data['content']).decode('utf-8') if 'content' in readme_data else ''

    # Process README content to remove newlines and handle quotes
    readme_content = readme_content.replace('\n', '换行').replace('\r', '回车')

    # Fetch the main programming language
    main_language = get_main_language(repo_url)

    # Append the data to the list
    data_list.append({
        'Project Name': project_name,
        'Owner Name': owner_name,
        'Owner Location': location,
        'Creation Time': created_at,
        'Stars': stars_count,
        'Forks': forks_count,
        'Watching': watching_count,  # 添加watching数目信息
        'Commits': total_commits,
        'Relative Time': relative_time,
        'About': about,
        'Topics': ', '.join(topics),
        'Main Language': main_language,
        'Readme': f'"{readme_content}"'
    })

    # Add a delay between requests to avoid hitting the rate limit
    time.sleep(8)

# Convert the list of data to a DataFrame
df = pd.DataFrame(data_list)

# Save the DataFrame to a CSV file with UTF-8 encoding
df.to_csv('~/Desktop/github_projects_data.csv', index=False, encoding='utf-8-sig')