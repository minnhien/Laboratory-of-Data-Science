import json
import csv
import os
import random
import calendar
import xml.etree.ElementTree as ET

class ETLPipeline:
    def __init__(self, input_xml, input_json, output_dir, output_xml):
        # 1. Path Configuration
        self.input_xml = input_xml
        self.input_json = input_json
        self.output_dir = output_dir
        self.output_xml_path = os.path.join(output_dir, output_xml)
        
        # Create output directory incase not exist
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        # 2. Variables
        # Geography
        self.geo_lookup_map = {}
        self.geography_table = []
        self.geo_counter = 1
        
        # Artist
        self.artist_final_data = []
        self.existing_ids = set()
        self.existing_names_map = {}
        self.artist_db_id_map = {}
        self.artist_csv_table = []
        
        # Other Dimensions
        self.album_map = {}
        self.album_table = []
        self.alb_counter = 1
        
        self.cat_map = {}
        self.cat_table = []
        self.cat_counter = 1
        
        self.lyrics_map = {}
        self.lyrics_table = [[-1, ""]]
        self.lyrics_counter = 1
        
        self.date_ids_set = set([-1])
        self.date_table = [[-1, None, None, None, None, None, None]]
        
        # Fact & Bridge
        self.fact_table = []
        self.song_artist_bridge = []
        self.song_counter = 1

    #FUNCTIONS
    @staticmethod
    def safe_str(value):
        if value is None: return None
        s = str(value).strip()
        if s == "" or s.lower() == "nan" or s.lower() == "na":
            return None
        return s

    @staticmethod
    def safe_int(value):
        if value is None: return None
        try:
            return int(float(str(value).strip()))
        except:
            return None

    def generate_random_id(self):
        while True:
            new_id = f"ART{random.randint(10000000, 99999999)}"
            if new_id not in self.existing_ids:
                return new_id

    @staticmethod
    def transform_gender(val):
        s = ETLPipeline.safe_str(val)
        if not s: return None
        if s.upper() == 'M': return 'Male'
        if s.upper() == 'F': return 'Female'
        return s

    @staticmethod
    def transform_explicit(val):
        try:
            v = int(float(str(val).strip()))
            return 'yes' if v == 1 else 'no'
        except:
            return 'no'

    @staticmethod
    def transform_is_group(val):
        s = ETLPipeline.safe_str(val)
        if not s: return None
        if s == '1': return 'yes'
        if s == '0': return 'no'
        return s.lower()

    def get_or_create_geo_id(self, city, prov, reg, cntry, h3):
        v_city = self.safe_str(city)
        v_prov = self.safe_str(prov)
        v_reg = self.safe_str(reg)
        v_cntry = self.safe_str(cntry)
        v_h3 = self.safe_str(h3)

        # If there is absolutely no data, return None.
        if not any([v_city, v_prov, v_reg, v_cntry, v_h3]):
            return None
        
        key = (v_city, v_prov, v_reg, v_cntry, v_h3)
        
        if key not in self.geo_lookup_map:
            self.geo_lookup_map[key] = self.geo_counter
            self.geography_table.append([self.geo_counter, key[0], key[1], key[2], key[3], key[4]])
            self.geo_counter += 1
        return self.geo_lookup_map[key]

    #CORE PROCESSING METHODS

    def load_data(self):
        print("--- Part 1: Loading Data ---")
        # Load XML
        try:
            tree = ET.parse(self.input_xml)
            root = tree.getroot()
            print(f"-> Loaded XML: {self.input_xml}")
        except Exception as e:
            print(f"Error reading XML (Creating new): {e}")
            root = ET.Element("root")
            tree = ET.ElementTree(root)
        
        # Load JSON
        tracks_data = []
        try:
            with open(self.input_json, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
                if isinstance(raw_data, dict):
                    for v in raw_data.values():
                        if isinstance(v, list):
                            tracks_data = v
                            break
                    if not tracks_data: tracks_data = []
                else:
                    tracks_data = raw_data
            print(f"-> Loaded JSON: {self.input_json} ({len(tracks_data)} tracks)")
        except Exception as e:
            print(f"Error reading JSON: {e}")
            tracks_data = []
            
        return tree, root, tracks_data

    def process_artists(self, root, tracks_data):
        print("\nPart 2: Processing Geography & Artists")
        
        # 1. Process XML Artists
        for row in root.findall('row'):
            a_id = self.safe_str(row.find('id_author').text)
            name = self.safe_str(row.find('name').text)
            if not a_id: continue

            cur_geo_id = self.get_or_create_geo_id(
                row.find('city').text if row.find('city') is not None else None,
                row.find('province').text if row.find('province') is not None else None,
                row.find('region').text if row.find('region') is not None else None,
                row.find('country').text if row.find('country') is not None else None,
                row.find('h3').text if row.find('h3') is not None else None
            )

            birth_geo_id = self.get_or_create_geo_id(
                row.find('birth_place').text if row.find('birth_place') is not None else None,
                row.find('birth_province').text if row.find('birth_province') is not None else None,
                row.find('birth_region').text if row.find('birth_region') is not None else None,
                row.find('birth_country').text if row.find('birth_country') is not None else None,
                row.find('birth_h3').text if row.find('birth_h3') is not None else None
            )

            birth_date_val = self.safe_str(row.find('birth_date').text if row.find('birth_date') is not None else None)

            artist_obj = {
                'id_author': a_id,
                'name': name,
                'gender': self.transform_gender(row.find('gender').text if row.find('gender') is not None else None),
                'is_group': self.transform_is_group(row.find('is_group').text if row.find('is_group') is not None else None),
                'birth_date': birth_date_val,
                'active_start': self.safe_str(row.find('active_start').text if row.find('active_start') is not None else None),
                'active_end': self.safe_str(row.find('active_end').text if row.find('active_end') is not None else None),
                'current_geo_id': cur_geo_id,
                'birth_geo_id': birth_geo_id
            }
            
            self.artist_final_data.append(artist_obj)
            self.existing_ids.add(a_id)
            if name: self.existing_names_map[name.lower()] = a_id

        # 2. Process Featured Artists
        added_feat_count = 0
        default_geo_id = self.get_or_create_geo_id(None, None, None, None, None)

        for track in tracks_data:
            feat_str = track.get('featured_artists', '')
            if not feat_str or str(feat_str).lower() == 'nan' or str(feat_str).strip() == "[]":
                continue

            clean_str = str(feat_str).replace('[','').replace(']','').replace("'", "").replace('"', "")
            feat_names = [n.strip() for n in clean_str.split(',') if n.strip()]

            for name in feat_names:
                name_lower = name.lower()
                if name_lower in self.existing_names_map: continue 
                
                # Logic: Partial Match (As requested)
                is_partial = False
                for ex_name in self.existing_names_map.keys():
                    if name_lower in ex_name: 
                        is_partial = True
                        break
                if is_partial: continue

                new_id = self.generate_random_id()
                
                # Update XML Tree directly
                new_row = ET.SubElement(root, 'row')
                ET.SubElement(new_row, 'id_author').text = new_id
                ET.SubElement(new_row, 'name').text = name
                ET.SubElement(new_row, 'is_group').text = "" 
                
                artist_obj = {
                    'id_author': new_id,
                    'name': name,
                    'gender': None,
                    'is_group': None,
                    'birth_date': None, 
                    'active_start': None,
                    'active_end': None,
                    'current_geo_id': default_geo_id,
                    'birth_geo_id': default_geo_id
                }
                self.artist_final_data.append(artist_obj)
                self.existing_names_map[name_lower] = new_id
                self.existing_ids.add(new_id)
                added_feat_count += 1
        
        print(f"-> Processed Artists: {len(self.artist_final_data)} (Added {added_feat_count} new featured).")

    def process_dimensions_facts(self, tracks_data):
        print("\nPart 3: Dimensions & Fact")
        
        # Prepare Artist CSV Table
        artist_counter = 1
        for art in self.artist_final_data:
            self.artist_db_id_map[art['id_author']] = artist_counter
            self.artist_csv_table.append([
                artist_counter,
                art['current_geo_id'],
                art['birth_geo_id'],
                art['id_author'],
                art['name'],
                art['gender'],
                art['is_group'],      
                art['birth_date'],    
                art['active_start'], 
                art['active_end']    
            ])
            artist_counter += 1

        for track in tracks_data:
            # ALBUM 
            a_id = track.get('id_album')
            if a_id and a_id not in self.album_map:
                self.album_map[a_id] = self.alb_counter
                self.album_table.append([
                    self.alb_counter, a_id, self.safe_str(track.get('album_name')), self.safe_str(track.get('album_release_date'))
                ])
                self.alb_counter += 1
            
            # DATE 
            full_date = track.get('full_date')
            date_id = -1
            if full_date:
                try:
                    val = int(str(full_date).replace('-','').replace('.','').strip())
                    if val > 19000000: date_id = val
                except: pass
            
            if date_id not in self.date_ids_set:
                year_val = self.safe_int(track.get('year'))
                quarter_val = self.safe_int(track.get('quarter'))
                week_val = self.safe_int(track.get('week_of_year'))
                the_day_val = self.safe_str(track.get('the_day'))
                if not the_day_val: 
                    the_day_val = self.safe_str(track.get('day_of_week'))

                m_hier = track.get('month_hierarchy')
                m_name = None
                m_int = self.safe_int(m_hier)
                if m_int and m_int > 100:
                     m_int = m_int % 100 
                     try: m_name = calendar.month_name[m_int]
                     except: pass
                else:
                    m_int = None 

                self.date_table.append([
                    date_id, the_day_val, week_val, m_int, quarter_val, year_val, m_name
                ])
                self.date_ids_set.add(date_id)

            # CATEGORY
            mel = self.safe_str(track.get('melodic_type'))
            lyr = self.safe_str(track.get('lyrics_topic'))
            cat_key = (mel, lyr)
            if cat_key not in self.cat_map:
                self.cat_map[cat_key] = self.cat_counter
                self.cat_table.append([self.cat_counter, mel, lyr])
                self.cat_counter += 1
                
            # LYRICS
            raw_lyrics = self.safe_str(track.get('lyrics'))
            
            if raw_lyrics:
                if raw_lyrics not in self.lyrics_map:
                    self.lyrics_map[raw_lyrics] = self.lyrics_counter
                    self.lyrics_table.append([self.lyrics_counter, raw_lyrics])
                    self.lyrics_counter += 1
                lyrics_id = self.lyrics_map[raw_lyrics]
            else:
                lyrics_id = -1
                
            # FACT TABLE
            explicit_val = self.transform_explicit(track.get('explicit')) 
            
            fact_row = [
                self.song_counter,                     
                date_id,                          
                self.album_map.get(a_id),              
                self.cat_map.get(cat_key),
                lyrics_id, 
                self.safe_str(track.get('id')),        
                self.safe_str(track.get('title')),
                self.safe_int(track.get('duration_ms')),
                self.safe_int(track.get('track_number')),
                self.safe_int(track.get('streams@1month')),
                explicit_val                      
            ]
            self.fact_table.append(fact_row)
            
            # BRIDGE TABLE
            p_id_str = track.get('id_artist')
            if p_id_str in self.artist_db_id_map:
                self.song_artist_bridge.append([self.song_counter, self.artist_db_id_map[p_id_str], 'Primary'])
            
            feat_str = track.get('featured_artists')
            if feat_str and str(feat_str).strip() != "[]":
                clean_str = str(feat_str).replace('[','').replace(']','').replace("'", "").replace('"', "")
                names = [n.strip().lower() for n in clean_str.split(',') if n.strip()]
                
                for n_lower in names:
                    f_db_id = None
                    if n_lower in self.existing_names_map:
                        f_auth_id = self.existing_names_map[n_lower]
                        f_db_id = self.artist_db_id_map.get(f_auth_id)
                    
                    if not f_db_id:
                        for ex_name, ex_auth_id in self.existing_names_map.items():
                            if n_lower in ex_name:
                                f_db_id = self.artist_db_id_map.get(ex_auth_id)
                                break
                    
                    if f_db_id:
                        if p_id_str in self.artist_db_id_map and f_db_id == self.artist_db_id_map[p_id_str]:
                            continue
                        self.song_artist_bridge.append([self.song_counter, f_db_id, 'Featured'])

            self.song_counter += 1

        self.song_artist_bridge.sort(key=lambda x: x[0])

    def write_csv(self, name, headers, data):
        path = os.path.join(self.output_dir, name)
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                w.writerow(headers)
                w.writerows(data)
            print(f"-> Saved {name}")
        except Exception as e:
            print(f"Error saving {name}: {e}")

    def save_files(self, tree):
        print("\nPart 4: Saving files")
        # Save XML
        if hasattr(ET, 'indent'): ET.indent(tree, space="\t", level=0)
        tree.write(self.output_xml_path, encoding='utf-8', xml_declaration=True)

        # Save CSVs
        self.write_csv('artist_geography.csv', 
                  ['artist_geo_id', 'city', 'province', 'region', 'country', 'h3'], 
                  self.geography_table)

        self.write_csv('artist.csv',
                  ['artist_id', 'current_geo_id', 'birth_geo_id', 'id_author', 'name', 'gender', 'is_group', 'birth_date', 'active_start', 'active_end'],
                  self.artist_csv_table)

        self.write_csv('album.csv', 
                  ['album_id', 'id_album', 'album_name', 'album_release_date'], 
                  self.album_table)

        self.write_csv('date.csv', 
                  ['date_id', 'the_day', 'week_of_year', 'month', 'quarter', 'year', 'month_name'], 
                  self.date_table)

        self.write_csv('category.csv', 
                  ['category_id', 'melody_cat', 'lyrics_cat'], 
                  self.cat_table)

        self.write_csv('lyrics.csv',
                  ['lyrics_id', 'lyrics'],
                  self.lyrics_table)

        self.write_csv('Published_song_fact.csv', 
                  ['song_id', 'date_id', 'album_id', 'category_id', 'lyrics_id', 'track_id', 'title', 'duration', 'track_number', 'stream_1month', 'explicit'], 
                  self.fact_table)

        self.write_csv('song_artist.csv', 
                  ['song_id', 'artist_id', 'artist_role'], 
                  self.song_artist_bridge)

    def run(self):
        tree, root, tracks_data = self.load_data()
        self.process_artists(root, tracks_data)
        self.process_dimensions_facts(tracks_data)
        self.save_files(tree)
        print("\nCOMPLETE")

#EXECUTION BLOCK
if __name__ == "__main__":
    pipeline = ETLPipeline(
        input_xml='artists_enriched.xml',
        input_json='tracks_final_04_12.json',
        output_dir='data_splitting_v2',
        output_xml='artists_updated.xml'
    )
    pipeline.run()