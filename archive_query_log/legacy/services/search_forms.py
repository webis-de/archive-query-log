import re
import pandas as pd
from tqdm import tqdm
from requests_html import HTMLSession
from bs4 import BeautifulSoup
import argparse

pattern = re.compile(r'(?i).*search.*')


# noinspection PyUnresolvedReferences,PyBroadException
class SearchFormIdentifier:
    """
    Class that takes in a CSV-file containing services. The file needs
    to have the following columns:
    - rank
    - service (name with TLD e.g. 'amazon.com')
    - TLD
    The process_services method will look for input fields, search forms
    and search divs on the corresponding website,
    indicate if the service has such a field as well as document
    any HMTL-snippet found during the search
    """

    def __init__(self, csv_file='./ranked_services.csv', outfile_num=0,
                 start_row=0, end_row=None):
        self.out_df = None
        self.df = pd.read_csv(csv_file, header=None)
        self.df.columns = ['rank', 'service', 'tld']

        if end_row is None:
            end_row = len(self.df)
        self.df = self.df[start_row:end_row]

        self.out_file = f'./search_forms_{outfile_num}.csv'
        self.session = HTMLSession()

    def process_services(self):
        """
        Use pd.DataFrame.progress_apply to run the method check_url
        on all services.
        Store the results in an attribute out_df and save it in a csv-File.
        """
        tqdm.pandas()
        self.out_df = self.df.copy(deep=True)

        # Search for the HTML elements and split the results
        # into separate columns
        self.out_df['tmp'] = self.df['service'].progress_apply(
            func=self.check_url)
        self.out_df[['input', 'search_form', 'search_div', 'input_snippets',
                     'form_snippets', 'div_snippets']] = \
            pd.DataFrame(self.out_df['tmp'].tolist(), index=self.out_df.index)
        self.out_df.drop('tmp', axis=1, inplace=True)
        self.out_df.to_csv(self.out_file)

    def check_url(self, url: str):
        """
        Method to take in a service URL and look for
        any relevant tags in the HTML.
        It will look for any input tag and div or form with an id that
        has the term 'search' in it

        :param      url:                Service URL to be processed
        :return:    found_input:        Boolean
                    found_search_form:  Boolean
                    found_search_div:   Boolean
                    input_snippets:     List of identified HTML-snippets
                    form_snippets:      List of identified HTML-snippets
                    div_snippets:       List of identified HTML-snippets
        """

        url = 'https://' + url if 'http' not in url else url

        # If regular requesting fails, try to get a recent snapshot
        # in the internet archive
        try:
            response = self.session.get(url, timeout=10)
        except Exception:
            try:
                response = self.get_internet_archive_html(url=url)
            except Exception:
                return None, None, None

        try:
            html = response.html.html
        except Exception:
            return None, None, None

        # Render JavaScript necessary
        if '<script>' in html:
            try:
                response.html.render(timeout=10)
                html = response.html.html
            except Exception:
                return None, None, None

        # Look for elements with the pattern in them and save the snippets
        soup = BeautifulSoup(html, 'html.parser')
        found_input, input_snippets = find_input_tag(soup=soup)
        found_search_form, form_snippets = find_search_tag(
            soup=soup, tag='form')
        found_search_div, div_snippets = find_search_tag(soup=soup, tag='div')

        return found_input, found_search_form, found_search_div, \
            input_snippets, form_snippets, div_snippets

    def get_internet_archive_html(self, url: str, year=2022, byte_digits=4):
        """
        Method to get the response for a URL from the Internet Archive.
        It will return the most recent snapshot from the specified year
        with a minimum size

        :param url:             URL for which to find a snapshot
        :param year:            The desired year for snapshots
        :param byte_digits:     Defines the minimum size with a leading 5.
                                Examples byte_digits=4 -> Bytes >= 5,000;
                                byte_digits=5 -> Bytes >= 50,000
        :return:                The response from the Internet Archive Snapshot
        """
        # Get the snapshots with a minimum number of bytes
        # from the specified year and extract the timestamp of the most recent
        search_url = f'https://web.archive.org/cdx/search/cdx' \
                     f'?url={url}&fl=original,timestamp,length&from={year}' \
                     f'&filter=mimetype:text/html&filter=statuscode:200' \
                     f'&filter=length:.*[5-9][0-9]%7B{byte_digits - 1},%7D.*'
        try:
            response = self.session.get(search_url, timeout=10)
            snapshot_list = response.html.html.split('\n')
            timestamp = snapshot_list[-2].split(" ")[1]

            # Request the corresponding HTML
            ia_url = f'https://web.archive.org/web/{timestamp}/{url}/'
            return self.session.get(ia_url, timeout=10)
        except Exception as e:
            raise RuntimeError(
                'Failed to request an internet archive snapshot') from e

    def services_no_search(self):
        return self.out_df[(self.out_df['input'] is False) & (
                self.out_df['search_form'] is False) &
                           (self.out_df['search_div'] is False)]


def find_input_tag(soup: BeautifulSoup):
    """
    Function to look for HTML-Elements with the input tag
    :param      soup:           A bs4.BeautifulSoup instance with the HTML
        to conduct tag search on
    :return:    found:          Boolean to indicate if search was successful
                snippet_list:   List of matching HTML snippets that were found

    """
    snippet_list = soup.findAll(re.compile(r'(?i).*input.*'))
    found = True if len(snippet_list) > 0 else False
    return found, snippet_list


def find_search_tag(soup: BeautifulSoup, tag='form'):
    """
    Function to look for HTML-Elements with the specified tag
    that contain the pattern "search" in some way
    :param      soup:           A bs4.BeautifulSoup instance with the HTML
                                to conduct tag search on
                tag:            Name of relevant tags
    :return:    found:          Boolean to indicate if search was successful
                snippet_list:   List of matching HTML snippets that were found

    """
    snippet_list = soup.findAll(tag, {"id": pattern})
    found = True if len(snippet_list) > 0 else False
    return found, snippet_list


def main():
    # Parse input
    parser = argparse.ArgumentParser(
        prog='Search form identification',
        description='Takes in a CSV-File of services '
                    'and looks for search forms in their HTML')
    parser.add_argument('-f', '--csv_file', type=str)
    parser.add_argument('-o', '--outfile_num', type=str)
    parser.add_argument('-s', '--start_row', type=int)
    parser.add_argument('-e', '--end_row', type=int)
    args = parser.parse_args()

    # Set/Update default values
    csv_file = './alexa-top-1m-fused-domains-rrf-top-10000.csv' \
        if args.csv_file is None else args.csv_file
    outfile_num = "0" if args.outfile_num is None else args.outfile_num
    start_row = 0 if args.start_row is None else args.start_row
    end_row = None if args.end_row is None else args.end_row

    # Run the search for specified services
    identifier = SearchFormIdentifier(
        csv_file=csv_file, outfile_num=outfile_num,
        start_row=start_row, end_row=end_row
    )
    identifier.process_services()


if __name__ == "__main__":
    main()
