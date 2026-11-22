with source as (

    select * from {{ source('donkey_raw', 'vehicle_status') }}

),

renamed as (

    select
        vehicle_id,
        vehicle_type_id,
        station_id,
        lat as latitude,
        lon as longitude,
        is_reserved,
        is_disabled,
        last_reported,
        current_range_meters,
        current_fuel_percent,
        min(fetched_at) over (partition by _dlt_load_id) as snapshot_at

    from source

)

select * from renamed
