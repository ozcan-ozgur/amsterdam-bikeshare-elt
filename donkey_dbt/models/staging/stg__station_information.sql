with source as (

    select * from {{ source('donkey_raw', 'station_information') }}

),

names as (

    select *
    from {{ source('donkey_raw', 'station_information__name') }}
    where language = 'nl'

),

renamed as (

    select
        s.station_id,
        n.text as station_name,
        s.lat as latitude,
        s.lon as longitude,
        s.region_id,
        s.is_virtual_station,
        s.capacity,
        s.address,
        s.post_code,
        s.rental_uris__android,
        s.rental_uris__ios,
        s.fetched_at

    from source as s
    left join names as n
        on s._dlt_id = n._dlt_parent_id

)

select * from renamed
