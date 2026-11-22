with source as (

    select * from {{ source('donkey_raw', 'station_status') }}

),

renamed as (

    select
        station_id,
        num_vehicles_available,
        num_docks_available,
        is_installed,
        is_renting,
        is_returning,
        last_reported,
        min(fetched_at) over (partition by _dlt_load_id) as snapshot_at

    from source

)

select * from renamed
