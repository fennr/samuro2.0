import hikari
import httpx

from etc import constants as const
from models.heroes import HotsHero


async def weekly_rotation() -> hikari.Embed:
    url = 'https://nexuscompendium.com/api/currently/herorotation'
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.246'
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url, headers={'User-Agent': f'{user_agent}'}
        )
    data = response.json()
    start_date = data['RotationHero']['StartDate']
    end_date = data['RotationHero']['EndDate']
    heroes = data['RotationHero']['Heroes']
    hero_links = ''
    for hero_name in heroes:
        hero = HotsHero(str(hero_name['Name']))
        hero_links = (
            hero_links + '[' + hero.ru + '](' + hero_name['URL'] + '), '
        )
    hero_links = hero_links[:-2]

    embed = hikari.Embed(
        title='{} : {} - {}'.format('Ротация героев', start_date, end_date),
        description=hero_links,
        color=const.EMBED_BLUE,
    )
    return embed
