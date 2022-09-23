-- Copyright (C) 2022-present HyperGH

-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.

-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.

-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see: https://www.gnu.org/licenses


-- Creation of all tables necessary for the bot to function

CREATE TABLE IF NOT EXISTS schema_info
(
    schema_version integer NOT NULL,
    PRIMARY KEY (schema_version)
);


-- Insert schema version into schema_info table if not already present
DO
$do$
DECLARE _schema_version integer;
BEGIN
    SELECT 3 INTO _schema_version; -- The current schema version, change this when creating new migrations

	IF NOT EXISTS (SELECT schema_version FROM schema_info) THEN
		INSERT INTO schema_info (schema_version) 
		VALUES (_schema_version); 
	END IF;
END
$do$;

CREATE TABLE IF NOT EXISTS global_config
(
    guild_id bigint NOT NULL,
    prefix text[],
    PRIMARY KEY (guild_id),
    season varchar default '01'
);

CREATE TABLE IF NOT EXISTS users
(
    user_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    flags json,
    warns integer NOT NULL DEFAULT 0,
    notes text[],
    PRIMARY KEY (user_id, guild_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS preferences
(
    user_id bigint NOT NULL,
    timezone text NOT NULL DEFAULT 'UTC',
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS blacklist
(
    user_id bigint NOT NULL,
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS mod_config
(
    guild_id bigint NOT NULL,
    dm_users_on_punish bool NOT NULL DEFAULT true,
    is_ephemeral bool NOT NULL DEFAULT false,
    automod_policies json NOT NULL DEFAULT '{}',
    PRIMARY KEY (guild_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS reports
(
    guild_id bigint NOT NULL,
    is_enabled bool NOT NULL DEFAULT false,
    channel_id bigint,
    pinged_role_ids bigint[] DEFAULT '{}',
    PRIMARY KEY (guild_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS timers
(
    id serial NOT NULL,
    guild_id bigint NOT NULL,
    user_id bigint NOT NULL,
    channel_id bigint,
    event text NOT NULL,
    expires bigint NOT NULL,
    notes text,
    PRIMARY KEY (id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS button_roles
(
    guild_id bigint NOT NULL,
    entry_id serial NOT NULL,
    channel_id bigint NOT NULL,
    msg_id bigint NOT NULL,
    emoji text NOT NULL,
    label text,
    style text,
    role_id bigint NOT NULL,
    mode smallint NOT NULL DEFAULT 0,
    add_title text,
    add_desc text,
    remove_title text,
    remove_desc text,
    PRIMARY KEY (guild_id, entry_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags
(
    guild_id bigint NOT NULL,
    tagname text NOT NULL,
    owner_id bigint NOT NULL,
    creator_id bigint, -- This may be null for tags that were not tracked for this.
    uses integer NOT NULL DEFAULT 0,
    aliases text[],
    content text NOT NULL,
    PRIMARY KEY (guild_id, tagname),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS log_config
(
    guild_id bigint NOT NULL,
    log_channels json,
    color bool NOT NULL DEFAULT true,
    PRIMARY KEY (guild_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS starboard
(
    guild_id bigint NOT NULL,
    is_enabled bool NOT NULL DEFAULT false,
    star_limit smallint NOT NULL DEFAULT 5,
    channel_id bigint,
    excluded_channels bigint[] DEFAULT '{}',
    PRIMARY KEY (guild_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS starboard_entries
(
    guild_id bigint NOT NULL,
    channel_id bigint NOT NULL,
    orig_msg_id bigint NOT NULL,
    entry_msg_id bigint NOT NULL,
    PRIMARY KEY (guild_id, channel_id, orig_msg_id),
    FOREIGN KEY (guild_id)
        REFERENCES global_config (guild_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS players
(
    id bigint NOT NULL,
    guild_id bigint NOT NULL,
    btag varchar(20) NOT NULL,
    mmr int DEFAULT 2200,
    league league_type DEFAULT 'Bronze',
    division int DEFAULT 0,
    team int DEFAULT NULL,
    PRIMARY KEY (id, guild_id, btag)
);

CREATE TABLE IF NOT EXISTS event_history
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
    delta_mmr integer default 6,
    win_points integer default 4,
    lose_points integer default 1,
    admin     varchar,
    type      varchar default '5x5'::character varying,
    season    varchar,
    map       varchar default 'unknown'
);

create table IF NOT EXISTS event_log
(
    id        bigint                                  not null,
    guild_id  bigint                                  not null,
    event_id  integer                                 not null
        constraint event_log_event_history_event_id_fk
            references event_history (event_id)
            on delete cascade,
    winner    boolean default false,
    points    integer                                 not null,
    delta_mmr integer                                 not null,
    map       varchar default 'unknown'::character varying,
    season    varchar default '01'::character varying not null,
    constraint event_log_pk
        primary key (id, guild_id, event_id, season),
    constraint event_log_players_stats_id_guild_id_season_fk
        foreign key (id, guild_id, season) references players_stats
            on delete cascade
);

comment on table event_log is 'Все записи о проведенных матчах';

create table IF NOT EXISTS players_stats
(
    id        bigint                                     not null
        constraint players_stats_players_id_fk
            references players
            on delete cascade,
    guild_id  guild_id                                       not null,
    win       integer,
    lose      integer,
    points    integer,
    btag      battletag,
    winstreak integer default 0,
    max_ws    integer default 0,
    season    varchar default 'Season 01'::character varying not null,
    constraint players_stats_pk
        primary key (id, guild_id, season)
);

comment on table players_stats is 'Данные о победах и поражениях';

create table IF NOT EXISTS vote_log
(
    id       bigint,
    event_id integer
        constraint vote_log_event_history_event_id_fk
            references event_history (event_id)
            on delete cascade,
    won      boolean,
    constraint vote_log_pk
        unique (id, event_id)
);

comment on table vote_log is 'Таблица статистики по голосованиям';

create table IF NOT EXISTS votes
(
    id       bigint,
    event_id integer
        constraint votes_eventhistory_event_id_fk
            references "event_history" (event_id)
            on delete cascade,
    vote     winner_type,
    constraint votes_pk
        primary key (id, event_id)
);

comment on table "votes" is 'Таблица с открытыми голосованиями';



