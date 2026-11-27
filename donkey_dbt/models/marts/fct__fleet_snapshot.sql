{{
    config(
        materialized = 'incremental',
        unique_key = 'snapshot_at',
        on_schema_change = 'append_new_columns',
        partition_by = {'field': 'snapshot_at', 'data_type':'timestamp', 'granularity':'day'} if target.type == 'bigquery' else none
    )
}}

with vehicles as (

    select * from {{ ref('stg__vehicle_status') }}
    {% if is_incremental() %}

        where snapshot_at > (select max(snapshot_at) from {{ this }})
    {% endif %}
),

stations as (

    -- current station list: one row = one station (join does not fan out rows)
    select station_id from {{ ref('stg__station_information') }}
),

enriched as (

    select
        v.snapshot_at,
        v.vehicle_id,
        coalesce(v.is_disabled, false) as is_disabled,
        coalesce(v.is_reserved, false) as is_reserved,
        -- available if it is neither disabled nor reserved
        not coalesce(v.is_disabled or v.is_reserved, false) as is_available,
        -- unlisted station (21044, 37081, 37084) = depot / non-public location
        s.station_id is null as is_at_unlisted_station

    from vehicles as v
    left join stations as s
        on v.station_id = s.station_id

),

final as (

    select
        snapshot_at,
        count(*) as total_vehicles,
        sum(case when is_available then 1 else 0 end) as available_vehicles,
        sum(case when is_disabled then 1 else 0 end) as disabled_vehicles,
        sum(case when is_reserved then 1 else 0 end) as reserved_vehicles,
        sum(case when is_at_unlisted_station then 1 else 0 end) as vehicles_at_unlisted_stations

    from enriched
    group by 1

)

select * from final
