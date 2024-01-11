import requests

# Specify the API endpoint and query parameters
endpoint = 'http://export.arxiv.org/api/query'
params = {
    'search_query': 'cat:cs.CV OR cat:cs.AI',
    'start': 0,  # Starting index of the results
    'max_results': 5,  # Maximum number of results to retrieve
    'sortBy': 'submittedDate',  # Sort by submitted date
    'sortOrder': 'descending'  # Sort in descending order
}

# Send the API request
response = requests.get(endpoint, params=params)

# Check if the request was successful
if response.status_code == 200:
    # Parse the XML response
    xml_data = response.text

    # Extract the titles and abstracts from the XML
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_data)
    ns = {'arxiv': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('arxiv:entry', ns)

    with open('arxiv_results.txt', 'w') as f:
        for entry in entries:
            title = entry.find('arxiv:title', ns).text
            abstract = entry.find('arxiv:summary', ns).text

            f.writelines(['\nTitle:' + title])
            f.writelines(['\nAbstract:' + abstract])
            f.writelines(['\n---\n'])
else:
    print('Request failed with status code:', response.status_code)
