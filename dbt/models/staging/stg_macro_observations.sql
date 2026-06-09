{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'macro']
) }}

with source as (

    select *
    from {{ source('raw', 'raw_macro_observations') }}

),

cleaned as (

    select
        upper(trim(series_id)) as series_id,
        cast(date as date) as date,
        cast(value as double) as value,
        source,
        cast(updated_at as timestamp) as updated_at
    from source
    where series_id is not null
      and date is not null

)

select *
from cleaned
