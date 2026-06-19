import io

def generate_flux_image(prompt, client):
    try:
        image = client.text_to_image(prompt, model="black-forest-labs/FLUX.1-schnell")
        bio = io.BytesIO()
        bio.name = 'image.jpeg'
        image.save(bio, 'JPEG')
        bio.seek(0)
        return bio
    except:
        return None
