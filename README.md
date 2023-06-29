# A package that downloads and manage Chromedriver

Created to be used in a project, this package is published to github 
for ease of management and installation across different modules.

### Installation
install from `github`

``` bash
pip install git+https://github.com/AresJef/ChromeDM.git
```

### How to Use
```python
from chromedm import ChromeDM
    cdm = ChromeDM(
        # Default cache directory: `~/chromedm/.drivers`.
        dir=None
        /or...
        # Custom cache directory: `/destop/chromedrivers`.
        dir="/destop/chromedrivers"
    )
    chromedriver = await cdm.install(
        # Match the latest driver version after 1 day.
        latest_version_interval = 86_400,
        # Use local proxy.
        proxy="http://127.0.0.1:7890",
        # Download timeout after 10 seconds.
        timeout=10,
        # Only cache the latest 20 drivers.
        max_cache=20,
    )
```

### Compatibility
Only support for python 3.10 and above.

### Acknowledgements
ChromeDM is based on several open-source repositories.

ChromeDM makes modification of the following open-source repositories:
- [webdriver_manager](https://github.com/SergeyPirogov/webdriver_manager)
