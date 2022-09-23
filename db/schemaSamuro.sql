-- Creation of all tables necessary for the bot to function

create type winner_type as enum ('blue', 'red');

create type league_type as enum ('Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Master', 'Grandmaster');

create domain guild_id as bigint;

create domain discord_id as bigint;

create domain battletag as varchar(20);

CREATE TABLE IF NOT EXISTS IF NOT EXISTS events
(
    time      char(19) not null
        constraint events_pk
            primary key,
    admin     char(22),
    winner    char(4),
    active    char,
    blue01    char(20),
    blue02    char(20),
    blue03    char(20),
    blue04    char(20),
    blue05    char(20),
    red01     char(20),
    red02     char(20),
    red03     char(20),
    red04     char(20),
    red05     char(20),
    delta_mmr integer
);

create sequence "teams_team_id_seq"
    as integer;

create sequence "event_history_event_id_seq"
    as integer;

create sequence "achievements_achiev_id_seq"
    as integer;

CREATE TABLE IF NOT EXISTS "teams"
(
    id      integer default nextval('"teams_team_id_seq"'::regclass) not null
        primary key,
    name    varchar,
    leader  discord_id,
    members integer default 1,
    points  integer default 0
);

comment on table "teams" is 'Таблица с данными команд';

alter sequence "teams_team_id_seq" owned by "teams".id;

CREATE TABLE IF NOT EXISTS "players"
(
    btag     battletag,
    id       discord_id not null
        constraint id_key
            primary key,
    guild_id guild_id,
    mmr      integer,
    league   league_type,
    division integer,
    team     integer
        constraint team_key
            references "teams"
            on update set null on delete set null
);

comment on table "players" is 'Таблица связей дискорд-батлнет и личных данных единых на все сервера';

CREATE TABLE IF NOT EXISTS "players_stat"
(
    id        discord_id not null
        constraint id_key
            references "players"
            on update cascade on delete cascade,
    guild_id  guild_id   not null,
    win       integer,
    lose      integer,
    points    integer,
    btag      battletag,
    winstreak integer default 0,
    max_ws    integer default 0,
    constraint id
        primary key (id, guild_id)
);

comment on table "players_stat" is 'Данные о победах и поражениях';

create unique index teams_name_uindex
    on "teams" (name);

create unique index teams_leader_uindex
    on "teams" (leader);

CREATE TABLE IF NOT EXISTS "event_history"
(
    time      timestamp,
    guild_id  guild_id,
    winner    winner_type,
    active    boolean,
    blue1     battletag,
    blue2     battletag,
    blue3     battletag,
    blue4     battletag,
    blue5     battletag,
    red1      battletag,
    red2      battletag,
    red3      battletag,
    red4      battletag,
    red5      battletag,
    event_id  serial,
    room_id   bigint,
    delta_mmr integer,
    points    integer,
    admin     varchar,
    type      varchar default '5x5'::character varying
);

comment on table "event_history" is 'Таблица проведенных ивентов';

alter sequence "event_history_event_id_seq" owned by "event_history".event_id;

create unique index eventhistory_event_id_uindex
    on "event_history" (event_id);

CREATE TABLE IF NOT EXISTS "achievements"
(
    id       integer default nextval('"achievements_achiev_id_seq"'::regclass) not null,
    guild_id guild_id                                                          not null,
    name     varchar,
    primary key (id, guild_id)
);

alter sequence "achievements_achiev_id_seq" owned by "achievements".id;

comment on table "achievements" is 'Таблица существующих достижений';

CREATE TABLE IF NOT EXISTS "user_achievements"
(
    id          discord_id,
    guild_id    guild_id,
    achievement integer,
    date        date,
    constraint stats_key
        foreign key (id, guild_id) references "players_stat"
            on update cascade on delete cascade,
    constraint achive_key
        foreign key (guild_id, achievement) references "achievements" (guild_id, id)
            on update cascade on delete cascade
);

comment on table "user_achievements" is 'Связи между игроком и достижениями';


CREATE TABLE IF NOT EXISTS "event_votes"
(
    id       discord_id,
    event_id integer
        constraint votes_eventhistory_event_id_fk
            references "event_history" (event_id)
            on delete cascade,
    vote     winner_type
);

comment on table "event_votes" is 'Таблица с открытыми голосованиями';

CREATE TABLE IF NOT EXISTS "event_votes_stats"
(
    id      discord_id,
    correct integer,
    wrong   integer
);

comment on table "event_votes_stats" is 'Таблица статистики по голосованиям';


CREATE TABLE IF NOT EXISTS "blacklist"
(
    id     discord_id not null
        constraint blacklist_pk
            primary key,
    name   varchar,
    reason varchar
);

create unique index blacklist_id_uindex
    on "blacklist" (id);


CREATE TABLE IF NOT EXISTS global_config
(
    guild_id guild_id NOT NULL,
    prefix text[],
    PRIMARY KEY (guild_id)
);


CREATE TABLE IF NOT EXISTS preferences
(
    user_id discord_Id NOT NULL,
    timezone text NOT NULL DEFAULT 'UTC',
    PRIMARY KEY (user_id)
);