import os
import re
import requests
import sys

START_MARKER = "<!-- CONTRIBUTIONS-START -->"
END_MARKER = "<!-- CONTRIBUTIONS-END -->"
TABLE_HEADER = "| Project | Description | Stars |"
TABLE_DIVIDER = "| --- | --- | --- |"


def sanitize_description(description):
    clean_desc = description.replace("|", "-").replace("\n", " ").strip()
    if len(clean_desc) > 60:
        return clean_desc[:57] + "..."
    return clean_desc


def format_row(contribution):
    return (
        f"| [{contribution['full_name']}]({contribution['url']}) | "
        f"{sanitize_description(contribution['desc'])} | ⭐ {contribution['stars']} |"
    )


def normalize_row(row_line):
    parts = [part.strip() for part in row_line.strip().strip("|").split("|")]
    if len(parts) < 3:
        return None

    project_cell = parts[0]
    desc_cell = parts[1]
    stars_cell = parts[-1]

    match = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", project_cell)
    if not match:
        return None

    full_name = match.group(1)
    url = match.group(2)
    stars_value = stars_cell.replace("⭐", "").strip()
    if not stars_value:
        stars_value = "0"

    normalized_row = f"| [{full_name}]({url}) | {desc_cell} | ⭐ {stars_value} |"
    return full_name, normalized_row


def parse_existing_projects(section_content):
    existing_projects = set()

    for line in section_content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| ["):
            continue

        normalized = normalize_row(stripped)
        if not normalized:
            continue

        full_name, _ = normalized
        if full_name in existing_projects:
            continue

        existing_projects.add(full_name)

    return existing_projects


def get_contributions(token, username):
    headers = {"Authorization": f"Bearer {token}"}
    query = """
    query($username: String!) {
      user(login: $username) {
        repositoriesContributedTo(first: 100, contributionTypes: [COMMIT], orderBy: {field: STARGAZERS, direction: DESC}, privacy: PUBLIC) {
          nodes {
            name
            nameWithOwner
            description
            url
            stargazerCount
            owner {
              login
            }
          }
        }
      }
    }
    """
    variables = {"username": username}
    request = requests.post('https://api.github.com/graphql', json={'query': query, 'variables': variables}, headers=headers)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception(f"Query failed to run by returning code of {request.status_code}. {query}")

def main():
    token = os.environ.get("GITHUB_TOKEN")
    username = os.environ.get("GITHUB_USERNAME")
    
    if not token:
        print("GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)
    if not username:
        print("GITHUB_USERNAME environment variable is not set.")
        sys.exit(1)

    try:
        result = get_contributions(token, username)
        if 'errors' in result:
             print(f"GraphQL errors: {result['errors']}")
             sys.exit(1)
             
        repos = result['data']['user']['repositoriesContributedTo']['nodes']
        
        contributions = []
        for repo in repos:
            owner = repo['owner']['login']
            name = repo['name']
            desc = repo['description'] if repo['description'] else "No description"
            url = repo['url']
            stars = repo['stargazerCount']
            if stars < 400:
                continue
            
            contributions.append({
                "full_name": f"{owner}/{name}",
                "desc": desc,
                "url": url,
                "stars": stars
            })

        readme_path = "README.md"
        with open(readme_path, "r") as f:
            content = f.read()

        if START_MARKER not in content or END_MARKER not in content:
            print("Markers not found in README.md")
            sys.exit(1)

        start_index = content.find(START_MARKER) + len(START_MARKER)
        end_index = content.find(END_MARKER)

        section_content = content[start_index:end_index]
        existing_projects = parse_existing_projects(section_content)
        current_projects = {c["full_name"] for c in contributions}
        new_projects = current_projects - existing_projects

        if not new_projects:
            print("No new projects found. README not changed.")
            return

        final_rows = [format_row(c) for c in contributions]
        markdown_output = "\n".join([TABLE_HEADER, TABLE_DIVIDER, *final_rows])
        new_content = content[:start_index] + "\n\n" + markdown_output + "\n\n" + content[end_index:]

        with open(readme_path, "w") as f:
            f.write(new_content)

        print(
            f"README.md fully rebuilt with {len(final_rows)} project(s). "
            f"Detected {len(new_projects)} new project(s)."
        )

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
