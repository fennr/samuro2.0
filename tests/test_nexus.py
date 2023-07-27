import hikari

from utils.nexuscompendium import weekly_rotation


async def test_rotation():
    embed = await weekly_rotation()
    assert isinstance(embed, hikari.Embed)
