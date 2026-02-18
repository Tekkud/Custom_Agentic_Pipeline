#MCP Import
from fastmcp import FastMCP

#Web Search Import
from ddgs import DDGS
import trafilatura
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse


mcp = FastMCP(name = "Server")


@mcp.tool()
def web_search(query, max_results, respect_robots=True):
    """Search and extract with robots.txt checking"""
    results = []
    
    with DDGS() as ddgs:
        search_results = ddgs.text(query, max_results=max_results * 2)  # Get extra in case some are filtered
        
        for result in search_results:
            if len(results) >= max_results:
                break
                
            url = result['href']
            
            # Check robots.txt if requested
            if respect_robots and not can_fetch(url):
                # print(f"Skipping {url} - disallowed by robots.txt")
                continue
            
            # Download and extract
            downloaded = trafilatura.fetch_url(url)
            
            if downloaded:
                # Extract with metadata
                text = trafilatura.extract(
                    downloaded,
                    include_comments=False,
                    include_tables=True,
                    include_links=False
                )
                
                # Get metadata
                metadata = trafilatura.extract_metadata(downloaded)
                
                if text:
                    results.append({
                        'title': result['title'],
                        'url': url,
                        'snippet': result['body'],
                        'full_text': text,
                        'word_count': len(text.split()),
                        'author': metadata.author if metadata else None,
                        'date': metadata.date if metadata else None,
                        'bot_friendly': True
                    })
    results_str = "Search Results:"
    for result in results:    
        results_str += f"TITLE:{result['title']}\nCONTEXT:{result['full_text'][:1000]}"
    results_str += "End of results."


    return results_str

def can_fetch(url, user_agent='*'):
    """Check robots.txt"""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except:
        return True

def main():
    # Initialize and run the server
    mcp.run(transport="stdio", show_banner = False, log_level = "error")


if __name__ == "__main__":
    main()