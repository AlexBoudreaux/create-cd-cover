from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sklearn.cluster import KMeans
import cv2
import numpy as np

def get_vibrant_color(image_path):
    image = cv2.imread(image_path)
    
    image_hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    pixels = image_hsv.reshape(-1, 3)
    
    kmeans = KMeans(n_clusters=5, n_init=10, random_state=0).fit(pixels)
    
    colors = kmeans.cluster_centers_
    
    vibrant_color = sorted(colors, key=lambda x: x[1]*x[2])[-1]
    
    vibrant_color_rgb = cv2.cvtColor(np.uint8([[list(map(int, vibrant_color))]]), cv2.COLOR_HSV2BGR)[0][0]
    
    return tuple(map(int, vibrant_color_rgb[::-1]))


def generate_wrap_around_cover(media_type, media_data, art_path):
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
    if sum(dominant_color) > 382:
        txt_color = (0, 0, 0)
    else:
        txt_color = (255, 255, 255)
    

    # FRONT--------------------------------------------------------------

    # Add art to top right corner of front cover
    img.paste(art, (690, 0))

    # Calculate text dimensions and positions
    bbox = d.textbbox((0, 0), f"{media_data['name']}", font=medium_fnt)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x_pos = front_dim[0] + spine_dim[0] + (back_dim[0] - text_width) // 2
    y_pos = (back_dim[1] - text_height) // 2 - 10

    # Draw a box with a border behind the text
    border_padding = 10  # You can adjust this value
    box_x1 = x_pos - border_padding
    box_y1 = y_pos - border_padding + 10
    box_x2 = x_pos + text_width + border_padding
    box_y2 = y_pos + text_height + border_padding + 10

    # Draw border box (slightly larger than the background box)
    d.rectangle([box_x1 - 2, box_y1 - 2, box_x2 + 2, box_y2 + 2], fill=(0, 0, 0), outline=None)

    # Draw background box
    d.rectangle([box_x1, box_y1, box_x2, box_y2], fill=dominant_color, outline=None)

    # Draw text on top of the box
    d.text((x_pos, y_pos), f"{media_data['name']}", font=medium_fnt, fill=txt_color)


    # SPINE--------------------------------------------------------------

    # Draw a rectangle for the spine
    d.rectangle([(front_dim[0], 0), (front_dim[0] + spine_dim[0], spine_dim[1])], fill=(255, 255, 255))
    
    # # Add rotated text to spine
    txt_img = Image.new('RGB', (640, 51), color=dominant_color)
    d = ImageDraw.Draw(txt_img)
    d.text((50, 0), f"{media_type}   •   {media_data['name']}", font=light_fnt, fill=txt_color)
    rotated_txt_img = txt_img.rotate(270, expand=1)
    img.paste(rotated_txt_img, (front_dim[0], 0))
    

    # BACK--------------------------------------------------------------

    # Load font
    medium_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Medium.ttf", 60)
    light_fnt = ImageFont.truetype("/Users/alexboudreaux/Library/Fonts/RedHatDisplay-Light.ttf", 60)

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
    
    # Calculate text dimensions for media type and name
    bbox_media_type = d.textbbox((0, 0), f"{media_type}", font=light_fnt)
    media_type_width = bbox_media_type[2] - bbox_media_type[0]
    media_type_height = bbox_media_type[3] - bbox_media_type[1]

    bbox_name = d.textbbox((0, 0), f"{media_data['name']}", font=medium_fnt)
    name_width = bbox_name[2] - bbox_name[0]
    name_height = bbox_name[3] - bbox_name[1]

    # Calculate positions for top-left corner
    x_pos_media_type = 30  # 10 pixels from the left edge
    y_pos_media_type = 10  # 10 pixels from the top edge

    x_pos_name = 30  # 10 pixels from the left edge
    y_pos_name = y_pos_media_type + media_type_height + 25  # 25 is arbitrary spacing, adjust as needed

    d = ImageDraw.Draw(img)  # Reset the ImageDraw object to main image
    d.text((x_pos_media_type, y_pos_media_type), f"{media_type}", font=light_fnt, fill=(255, 255, 255))

    divider_y = y_pos_media_type + media_type_height + 25  # 10 is arbitrary spacing, adjust as needed
    d.line([(x_pos_media_type + 7, divider_y), (x_pos_media_type + ((media_type_width + name_width) / 2), divider_y)], fill=(255, 255, 255), width=2)
    
    if bbox_name[2] < 600:
        d.text((x_pos_name, y_pos_name), f"{media_data['name']}", font=medium_fnt, fill=(255, 255, 255))
    else:
        # break name into two lines
        name_words = media_data['name'].split()
        first_line = ''
        second_line = ''
        for word in name_words:
            if len(first_line) < 2:
                first_line += word + ' '
            else:
                second_line += word + ' '
        d.text((x_pos_name, y_pos_name), f"{first_line}", font=medium_fnt, fill=(255, 255, 255))
        d.text((x_pos_name, y_pos_name + 60), f"{second_line}", font=medium_fnt, fill=(255, 255, 255))

    
    # Calculate positions to center text
    # x_pos_media_type = (back_dim[0] - media_type_width) // 2
    # y_pos_media_type = (back_dim[1] // 2) - media_type_height - 25  # 15 is arbitrary spacing, adjust as needed

    # x_pos_name = (back_dim[0] - name_width) // 2
    # y_pos_name = (back_dim[1] // 2) + 15  # 15 is arbitrary spacing, adjust as needed

    # d = ImageDraw.Draw(img)  # Reset the ImageDraw object to main image
    # d.text((x_pos_media_type, y_pos_media_type - 20), f"{media_type}", font=light_fnt, fill=(255, 255, 255))

    # divider_y = (y_pos_media_type + media_type_height + y_pos_name) // 2
    # d.line([(x_pos_media_type - 20 , divider_y), (x_pos_media_type + media_type_width + 20, divider_y)], fill=(255, 255, 255), width=2)
    
    # d.text((x_pos_name, y_pos_name), f"{media_data['name']}", font=medium_fnt, fill=(255, 255, 255))

    # Save Image
    img.save(f"{media_data['name']}_cover-tl.png")

# Example usage
if __name__ == "__main__":
    media_type = "Playlist"
    media_data = {'name': 'Gloria'}
    art_path = './playlist_art/playlist_cover_10.jpg'
    generate_wrap_around_cover(media_type, media_data, art_path)
