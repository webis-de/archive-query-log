import pandas as pd


def combine_alexa_manual(manual_csv: str, alexa_csv: str):
    """
    Function to combine the CSV created by search_forms.py
    with a manual collection of search engines
    :param manual_csv:  Path to the CSV containing a manual collection
        of search engines
    :param alexa_csv:   Path to the CSV containing the automatically
        created list of services
    :return:            A pd.DataFrame that combined both source CSVs
    """
    m_df = pd.read_csv(manual_csv)
    a_df = pd.read_csv(alexa_csv)
    a_df.drop("Unnamed: 0", axis=1, inplace=True)

    # Get identically formatted service names for both
    m_df["Service"] = m_df["Service"].str.lower()
    m_df.rename({"Service": "service"}, axis=1, inplace=True)
    a_df["service"] = a_df["service"].str.split(".").str[0]

    # Create new alexa df with unique service names and store
    # the duplicates to be added later
    a_df_unique = a_df.drop_duplicates(subset="service")
    a_df_merged = a_df.merge(a_df_unique, on=["rank", "rank"], how="left",
                             indicator=True)
    a_df_dup = a_df_merged[a_df_merged["_merge"] == "left_only"]
    a_df_dup = a_df_dup.loc[:, ~a_df_dup.columns.str.contains("_y")]
    a_df_dup.columns = a_df_dup.columns.str.rstrip("_x")
    a_df_dup.drop("_merge", axis=1, inplace=True)

    # Create merged df by performing an outer join on both df
    merged_df = pd.concat([a_df_unique.set_index("service"),
                           m_df.set_index("service")], axis=1,
                          join="outer").reset_index()
    merged_df = pd.concat([merged_df, a_df_dup], ignore_index=True)
    cols_reordered = ["rank", "service", "tld", "Search Category", "input",
                      "search_form", "search_div",
                      'input_snippets', 'form_snippets', 'div_snippets']
    merged_df = merged_df[cols_reordered]

    merged_df["rank"].fillna(99999, inplace=True)
    merged_df.sort_values("rank", inplace=True)
    return merged_df
