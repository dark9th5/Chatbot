from pipeline.config import MYSQL_CONFIG
import pymysql

conn = pymysql.connect(**MYSQL_CONFIG, cursorclass=pymysql.cursors.DictCursor)
cur = conn.cursor()
cur.execute("SELECT type, COUNT(*) AS c FROM graph_entities GROUP BY type ORDER BY c DESC")
rows = cur.fetchall()
print('Type counts:')
for r in rows:
    print(f"  {r['type']}: {r['c']}")

cur.execute("SELECT type, COUNT(DISTINCT name) AS names FROM graph_entities GROUP BY type ORDER BY names DESC")
print('\nDistinct names per type:')
for r in cur.fetchall():
    print(f"  {r['type']}: {r['names']}")

cur.execute("SELECT type, GROUP_CONCAT(DISTINCT SUBSTRING(name,1,80) SEPARATOR '|') AS sample FROM graph_entities GROUP BY type LIMIT 20")
print('\nSamples by type:')
for r in cur.fetchall():
    sample = (r['sample'] or '').split('|')[:10]
    print(f"  {r['type']}: {', '.join(sample)}")

conn.close()
