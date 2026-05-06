import pandas as pd
import psycopg2

DATABASE_URL = "postgresql://postgres.upszzapmustvggvoldms:32169250Gemma!@aws-0-eu-west-1.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(DATABASE_URL)

df = pd.read_sql("SELECT * FROM spese", conn)

print("\nDATABASE SPESE:\n")
print(df)

print("\nSALDO TOTALE:\n")

entrate = df[df["tipo"] == "entrata"]["importo"].sum()
uscite = df[df["tipo"] == "uscita"]["importo"].sum()

print(entrate - uscite)

print("\nUSCITE PER CATEGORIA:\n")

uscite_df = df[df["tipo"] == "uscita"]

print(
    uscite_df.groupby("categoria")["importo"].sum()
)