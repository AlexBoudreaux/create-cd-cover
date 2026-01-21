import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageOps
from sklearn.cluster import KMeans
import cv2
import numpy as np
import psycopg2
import os
from io import BytesIO
import requests

def get_vibrant_color(image_path):
    image = cv2.imread(image_path)
    
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    pixels = image_hsv.reshape(-1, 3)
    
    kmeans = KMeans(n_clusters=5, n_init=10, random_state=0).fit(pixels)
    
    colors = kmeans.cluster_centers_
    
    vibrant_color = sorted(colors, key=lambda x: x[1]*x[2])[-1]
    
    vibrant_color_rgb = cv2.cvtColor(np.uint8([[list(map(int, vibrant_color))]]), cv2.COLOR_HSV2BGR)[0][0]
    
    return tuple(map(int, vibrant_color_rgb[::-1]))

def fetch_media_data(conn):
    cur = conn.cursor()
    
    print("Fetching playlists...")
    cur.execute("""
    SELECT p.spotify_id, p.name, p.cover_image_url, 
           STRING_AGG(DISTINCT pa.artist_name, ', ') as artists
    FROM playlists p
    LEFT JOIN playlist_artists pa ON p.id = pa.playlist_id
    GROUP BY p.id
    """)
    playlists = cur.fetchall()
    print(f"Fetched {len(playlists)} playlists")
    
    # Fetch albums
    cur.execute("""
    SELECT spotify_id, name, artist, cover_image_url
    FROM albums
    """)
    albums = cur.fetchall()
    
    # Fetch artists
    cur.execute("""
    SELECT spotify_id, name, cover_image_url
    FROM artists
    """)
    artists = cur.fetchall()
    
    cur.close()
    return playlists, albums, artists

def download_image(url):
    print(f"Downloading {url}...")
    response = requests.get(url)
    return Image.open(BytesIO(response.content))

def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    current_line = words[0]
    for word in words[1:]:
        test_line = current_line + " " + word
        bbox = d.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)
    return lines

def create_acronym(text):
    words = text.split()
    return ''.join(word[0].upper() for word in words if word)

def generate_wrap_around_cover(media_data, art_path, output_filename):
    # Define dimensions
    front_dim = (640, 640)
    spine_dim = (50, 640)
    back_dim = (640, 640)
    
    # Create blank canvas
    total_width = front_dim[0] + spine_dim[0] + back_dim[0]
    total_height = front_dim[1]
    img = Image.new('RGB', (total_width, total_height), color='black')
    
    # Create ImageDraw object
    d = ImageDraw.Draw(img)
    
    # Load font
    medium_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Medium.ttf", 40)
    light_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Light.ttf", 40)

    # Download art
    art = Image.open(art_path)

    # find average color of art 
    dominant_color = get_vibrant_color(art_path)

    # find if color is light or dark
    if sum(dominant_color) > 590:
        txt_color = (0, 0, 0)
    else:
        txt_color = (255, 255, 255)

    # FRONT--------------------------------------------------------------

    # Resize the art to be smaller, keeping it centered
    resize_factor = 0.92  # Adjust this value as needed
    new_size = (int(art.width * resize_factor), int(art.height * resize_factor))
    resized_art = art.resize(new_size, Image.Resampling.LANCZOS)

    # Calculate new position to keep art centered
    x_offset = (art.width - resized_art.width) // 2
    y_offset = (art.height - resized_art.height) // 2
    new_position = (690 + x_offset, y_offset)

    # Background Color
    front_img = Image.new('RGB', front_dim, color=dominant_color)
    img.paste(front_img, (front_dim[0] + spine_dim[0], 0))

    # Load the drop shadow image
    drop_shadow = Image.open('assets/cover-art-dropshadow.png').convert('RGBA')

    # Resize the drop shadow image to match the size of the resized cover art
    drop_shadow_size = (resized_art.width + 145, resized_art.height + 145)
    drop_shadow = drop_shadow.resize(drop_shadow_size, Image.Resampling.LANCZOS)

    # Calculate the position to place the drop shadow
    drop_shadow_position = (new_position[0] - 72, new_position[1] - 72)

    # Paste the drop shadow onto the main image
    img.paste(drop_shadow, drop_shadow_position, mask=drop_shadow)

    # Cover Art
    img.paste(resized_art, new_position)

    # Text wrapping function for balanced lines
    def wrap_text_balanced(text, font, max_width):
        words = text.split()
        if len(words) == 1:
            return [text]
        
        lines = []
        current_line = words[0]
        current_width = d.textbbox((0, 0), current_line, font=font)[2]
        
        for word in words[1:]:
            word_width = d.textbbox((0, 0), word, font=font)[2]
            if current_width + word_width <= max_width:
                current_line += " " + word
                current_width += word_width
            else:
                lines.append(current_line)
                current_line = word
                current_width = word_width
        
        lines.append(current_line)
        
        # Balance lines if there are only two
        if len(lines) == 2:
            words = text.split()
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            
            # Check if moving one word improves balance
            if abs(len(line1) - len(line2)) > 1:
                if len(line1) > len(line2):
                    line1 = " ".join(words[:mid-1])
                    line2 = " ".join(words[mid-1:])
                else:
                    line1 = " ".join(words[:mid+1])
                    line2 = " ".join(words[mid+1:])
            
            lines = [line1, line2]
        
        return lines

    # Wrap the text
    wrapped_text = wrap_text_balanced(media_data['name'], medium_fnt, back_dim[0] - 260)

    # Calculate text dimensions and positions
    total_text_height = sum([d.textbbox((0, 0), line, font=medium_fnt)[3] - d.textbbox((0, 0), line, font=medium_fnt)[1] for line in wrapped_text])
    y_pos = (back_dim[1] - total_text_height) // 2 - 10

    # Load the backdrop image and convert it to RGBA mode
    backdrop = Image.open('assets/backdrop.png').convert('RGBA')

    # Resize the backdrop image while maintaining its aspect ratio
    max_size = (max([d.textbbox((0, 0), line, font=medium_fnt)[2] - d.textbbox((0, 0), line, font=medium_fnt)[0] for line in wrapped_text]) + 450, total_text_height + 450)  # Adjust the padding as needed
    backdrop.thumbnail(max_size)

    # Create a new image with the same size as the resized backdrop and fill it with the dominant color
    dominant_color_img = Image.new('RGBA', backdrop.size, dominant_color)

    # Multiply the backdrop image with the dominant color image
    colored_backdrop = ImageChops.multiply(backdrop, dominant_color_img)

    # Calculate the position to place the colored backdrop image
    backdrop_x = front_dim[0] + spine_dim[0] + (back_dim[0] - backdrop.width) // 2
    backdrop_y = y_pos - 200

    # Paste the colored backdrop image onto the main image
    img.paste(colored_backdrop, (backdrop_x, backdrop_y), mask=colored_backdrop)

    # Draw wrapped text on top of the colored backdrop
    for i, line in enumerate(wrapped_text):
        bbox = d.textbbox((0, 0), line, font=medium_fnt)
        text_width = bbox[2] - bbox[0]
        x_pos = front_dim[0] + spine_dim[0] + (back_dim[0] - text_width) // 2
        current_y_pos = y_pos + i * (bbox[3] - bbox[1])

        # Create a new RGBA image for the text shadow
        shadow_img = Image.new('RGBA', img.size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_img)

        # Draw the text shadow with a slight offset and black color
        shadow_offset = [3, 2]
        shadow_draw.text((x_pos + shadow_offset[0], current_y_pos + shadow_offset[1]), line, font=medium_fnt, fill=(0, 0, 0, 140))

        # Apply Gaussian blur to the shadow
        shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=4))

        # Paste the shadow onto the main image
        img.paste(shadow_img, mask=shadow_img)

        # Draw the text on top of the shadow
        d.text((x_pos, current_y_pos), line, font=medium_fnt, fill=txt_color)


    # SPINE--------------------------------------------------------------

    # Open the black and white texture to fit the spine dimensions
    bw_texture = Image.open('assets/texture.png').convert('L')  # Convert to grayscale ('L')

    # Lighten the dominant color
    lighter_dominant_color = tuple(min(255, int(x * 1.2)) for x in dominant_color)

    # Colorize the black and white texture using the lighter dominant color
    colored_texture = ImageOps.colorize(bw_texture, 'black', lighter_dominant_color)

    # Ensure both images are of the same size
    spine_area = img.crop((front_dim[0], 0, front_dim[0] + spine_dim[0], spine_dim[1]))
    if spine_area.size != colored_texture.size:
        colored_texture = colored_texture.resize(spine_area.size)

    # Ensure both images are of the same color mode
    if spine_area.mode != colored_texture.mode:
        colored_texture = colored_texture.convert(spine_area.mode)

    # Blend the colored texture with the existing spine
    blended_spine = ImageChops.blend(spine_area, colored_texture, alpha=1)  # Adjusted alpha

    # Paste the blended image back onto the spine area
    img.paste(blended_spine, (front_dim[0], 0))

    # Create a new RGBA image for the text with the same dimensions as the spine
    txt_img = Image.new('RGBA', (spine_dim[1], spine_dim[0]), (0, 0, 0, 0))  # Fully transparent background

    # Create a new RGBA image for the text shadow with the same dimensions as the spine
    shadow_img = Image.new('RGBA', (spine_dim[1], spine_dim[0]), (0, 0, 0, 0))  # Fully transparent background

    # Draw the text onto the shadow image
    shadow_draw = ImageDraw.Draw(shadow_img)

    # Replace all occurrences of textsize with textbbox
    def get_text_dimensions(text, font):
        bbox = d.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0], bbox[3] - bbox[1]

    # Function to create acronym
    def create_acronym(text):
        words = text.split()
        return ''.join(word[0].upper() for word in words if word)

    # Update the parts of the function that use textsize
    bullet_width, _ = get_text_dimensions("•", light_fnt)
    media_type_width, _ = get_text_dimensions(f"{media_data['type']} • ", light_fnt)
    
    # Calculate the position to place the "•" symbol
    bullet_position = (10, -3)

    # Draw the media type and "•" symbol using the light font with a slight offset and black color
    shadow_offset = [3, 2]
    shadow_draw.text((bullet_position[0] + shadow_offset[0], bullet_position[1] + shadow_offset[1]), f"{media_data['type']}  • ", font=light_fnt, fill=(0, 0, 0, 140))

    # Calculate the position to place the media name
    media_name_position = (bullet_position[0] + bullet_width + media_type_width, -3)

    # Use acronym if the name is too long
    spine_text = media_data['name']
    if get_text_dimensions(spine_text, medium_fnt)[0] > spine_dim[1] - media_name_position[0] - 20:  # 20px margin
        spine_text = create_acronym(spine_text)

    # Draw the media name using the medium font with a slight offset and black color
    shadow_draw.text((media_name_position[0] + shadow_offset[0], media_name_position[1] + shadow_offset[1]), spine_text, font=medium_fnt, fill=(0, 0, 0, 140))

    # Apply Gaussian blur to the shadow
    shadow_img = shadow_img.filter(ImageFilter.GaussianBlur(radius=3))

    # Rotate the shadow
    rotated_shadow_img = shadow_img.rotate(270, expand=1)

    # Draw the text onto the main text image
    d = ImageDraw.Draw(txt_img)
    d.text(bullet_position, f"{media_data['type']} • ", font=light_fnt, fill=txt_color)
    d.text(media_name_position, spine_text, font=medium_fnt, fill=txt_color)

    # Rotate the text
    rotated_txt_img = txt_img.rotate(270, expand=1)

    # Paste the rotated shadow onto the spine
    img.paste(rotated_shadow_img, (front_dim[0], 70), mask=rotated_shadow_img)

    # Paste the rotated text onto the spine, over the shadow
    img.paste(rotated_txt_img, (front_dim[0], 70), mask=rotated_txt_img)

    # Add logo to spine
    logo = Image.open('assets/spotify-logo.png')
    if logo.mode != 'RGBA':
        logo = logo.convert('RGBA')
    logo = logo.resize((62, 62))

    # Create a new image with white background for the shadow
    shadow = Image.new('RGBA', logo.size, (0, 0, 0, 0))

    # Draw a black circle for the shadow
    d = ImageDraw.Draw(shadow)
    d.ellipse((0, 0, shadow.size[0] - 23, shadow.size[1] - 23), fill=(0, 0, 0, 100))  # Reduced alpha to 80

    # Apply Gaussian blur to create the drop shadow effect
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=3))

    # Paste the shadow first
    img.paste(shadow, (645, 15), mask=shadow.split()[3])

    # Paste the logo on top of the shadow
    img.paste(logo, (635, 0), mask=logo.split()[3])
    

    # BACK--------------------------------------------------------------

    # Load font
    medium_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Medium.ttf", 60)
    light_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Light.ttf", 60)
    featured_artists_title_font = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Medium.ttf", 20)
    featured_artists_font = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Light.ttf", 20)

    # Convert art to 'RGBA' (if it's not already in that mode) to add an alpha channel
    if art.mode != 'RGBA':
        art = art.convert('RGBA')

    # Apply Gaussian Blur
    blurred_art = art.filter(ImageFilter.GaussianBlur(radius=15))

    # Add alpha channel for opacity (0-255, where 0 is fully transparent and 255 is fully opaque)
    alpha = Image.new('L', blurred_art.size, 128)  # Create a new alpha channel image with 50% opacity
    blurred_art.putalpha(alpha)  # Apply the alpha channel to the blurred image

    # Paste the semi-transparent blurred image onto the main image
    img.paste(blurred_art, (0 + 0, 0), mask=blurred_art.split()[3])  # 'mask' parameter uses the alpha channel as the mask

    # Load the drop shadow image
    flares = Image.open('assets/cover-art-flares.png').convert('RGBA')

    # Resize the drop shadow image to match the size of the resized cover art
    flares_size = (640, 640)
    flares = flares.resize(flares_size, Image.Resampling.LANCZOS)

    # Calculate the position to place the drop shadow
    flares_position = (0, 0)

    # Create a new image with the same size as the resized backdrop and fill it with the dominant color
    flare_color_img = Image.new('RGBA', flares_size, dominant_color)

    # Multiply the backdrop image with the dominant color image
    flare_backdrop = ImageChops.multiply(flares, flare_color_img)

    # Paste the drop shadow onto the main image
    img.paste(flare_backdrop, flares_position, mask=flares)
    
    d = ImageDraw.Draw(img)  # Reset the ImageDraw object to main image

    # Draw media type in top left corner
    x_pos_media_type = 30  # 30 pixels from the left edge
    y_pos_media_type = 10  # 10 pixels from the top edge
    d.text((x_pos_media_type, y_pos_media_type), f"{media_data['type']}", font=light_fnt, fill=txt_color)

    # Wrap text for media name
    max_width = back_dim[0] - 100  # Subtract some padding
    wrapped_name = wrap_text_balanced(media_data['name'], medium_fnt, max_width)

    # Calculate total height of wrapped text
    total_name_height = sum([d.textbbox((0, 0), line, font=medium_fnt)[3] - d.textbbox((0, 0), line, font=medium_fnt)[1] for line in wrapped_name])

    # Calculate starting y position for wrapped text
    y_pos_name = (back_dim[1] // 2) - (total_name_height // 2)

    if line in wrapped_name:
        y_pos_name -= 20

    # Draw wrapped text
    for line in wrapped_name:
        bbox_name = d.textbbox((0, 0), line, font=medium_fnt)
        name_width = bbox_name[2] - bbox_name[0]
        x_pos_name = (back_dim[0] - name_width) // 2
        d.text((x_pos_name, y_pos_name), line, font=medium_fnt, fill=txt_color)
        y_pos_name += bbox_name[3] - bbox_name[1] + 10

    featured_artists_title = "Featured Artists"

    # Calculate the dimensions of the featured artists section
    featured_artists_width = back_dim[0] - 60  # Subtract some padding
    featured_artists_height = 170

    # Calculate the position of the featured artists section
    featured_artists_x = (back_dim[0] - featured_artists_width) // 2
    featured_artists_y = 450  # Adjust this value as needed

    # Calculate the width of the title
    title_width = d.textbbox((0, 0), featured_artists_title, font=featured_artists_title_font)[2]

    # Draw the featured artists title
    title_x = featured_artists_x + (featured_artists_width - title_width) // 2
    d.text((title_x, featured_artists_y + 7), featured_artists_title, font=featured_artists_title_font, fill=txt_color)

    # Calculate the position and size of the divider line
    divider_width = 200
    divider_x = featured_artists_x + (featured_artists_width - divider_width) // 2
    divider_y = featured_artists_y + 45
    divider_height = 2

    # Draw the divider line
    d.line([(divider_x, divider_y), (divider_x + divider_width, divider_y)], fill=txt_color, width=divider_height)

    featured_artists_text = " • ".join(media_data['artists'].split(", ")[:8])

    # Calculate the maximum width and height for the featured artists names
    max_width = featured_artists_width + 20
    max_height = featured_artists_height - 60

    # Wrap the featured artists names to fit within the maximum width
    wrapped_text = textwrap.fill(featured_artists_text, width=max_width // featured_artists_font.getbbox("A")[2])

    # Split the wrapped text into lines
    lines = wrapped_text.split("\n")

    # Truncate the lines to fit within the maximum height
    truncated_lines = []
    current_height = 0
    for line in lines:
        line_height = featured_artists_font.getbbox(line)[1]
        if current_height + line_height <= max_height:
            truncated_lines.append(line)
            current_height += line_height
        else:
            truncated_lines[-1] = truncated_lines[-1][:-3] + "..."
            break

    # Join the truncated lines back into a single string
    truncated_text = "\n".join(truncated_lines)

    # Calculate the width of each line and find the maximum width
    line_widths = [d.textbbox((0, 0), line, font=featured_artists_font)[2] for line in truncated_lines]
    max_line_width = max(line_widths)

    # Calculate the position of the featured artists names
    featured_artists_text_x = featured_artists_x + (featured_artists_width - max_line_width) // 2
    featured_artists_text_y = divider_y + 20

    # Draw the featured artists names
    d.multiline_text((featured_artists_text_x, featured_artists_text_y), truncated_text, font=featured_artists_font, fill=txt_color, align="center")
    
    # Save Image
    img.save(output_filename)



def main():
    # print("Starting main function...")
    
    # Vercel Postgres connection
    vercel_db_url = "postgres://default:NZmvDbYd2K5R@ep-quiet-limit-a4370jzc-pooler.us-east-1.aws.neon.tech/verceldb?sslmode=require"
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(vercel_db_url)
        print("Connected successfully")
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return
    
    try:
        playlists, albums, artists = fetch_media_data(conn)
    except Exception as e:
        print(f"Error fetching media data: {e}")
        conn.close()
        return
    
    # Create the "Playlists CD Covers" folder if it doesn't exist
    output_folder = "Playlists CD Covers"
    os.makedirs(output_folder, exist_ok=True)
    
    print("Processing playlists...")
    for playlist in playlists:
        # print(f"Processing playlist: {playlist[1]}")
        media_data = {
            'spotify_id': playlist[0],
            'name': playlist[1],
            'type': 'PLAYLIST',
            'artists': playlist[3],
            'cover_image_url': playlist[2]
        }
        
        try:
            # Download the cover image
            cover_image = download_image(media_data['cover_image_url'])
            
            # Save the cover image temporarily
            temp_image_path = f"temp_{media_data['spotify_id']}.jpg"
            cover_image.save(temp_image_path)
            # print(f"Saved temporary image: {temp_image_path}")
            
            # Generate the CD cover
            # print("Generating CD cover...")
            output_filename = f"{output_folder}/{media_data['name']}.png"
            generate_wrap_around_cover(media_data, temp_image_path, output_filename)
            
            # Remove the temporary image file
            os.remove(temp_image_path)
            # print("Removed temporary image file")
            
            print(f"Generated cover for playlist: {media_data['name']}")
        except Exception as e:
            print(f"Error processing playlist {media_data['name']}: {e}")
    
    conn.close()
    print("Script completed")

if __name__ == "__main__":
    main()